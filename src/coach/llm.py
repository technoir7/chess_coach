from google import genai
from google.genai import types
import os
import logging
import concurrent.futures
from typing import Optional
from src.models import TruthPacket, CoachSpeechRules

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """Initialize LLM client with new google-genai package"""
        # Map config names to actual model identifiers
        model_mapping = {
            # Legacy mappings
            "Gemini_2_Flash": "gemini-2.0-flash",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-1.5-flash": "gemini-flash-latest",
            "gemini-1.5-pro": "gemini-pro-latest",
            
            # Gemini 2.5 and 3.0 models (using exact names from list_models)
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
            "gemini-3-flash": "gemini-3-flash-preview",
            
            # Gemma 3 models (adding -it suffix as found in list_models)
            "gemma-3-1b": "gemma-3-1b-it",
            "gemma-3-2b": "gemma-3-1b-it", # Fallback to 1b as 2b not in list
            "gemma-3-4b": "gemma-3-4b-it",
            "gemma-3-12b": "gemma-3-12b-it",
            "gemma-3-27b": "gemma-3-27b-it"
        }
        self.primary_model_name = model_mapping.get(model_name, model_name)
        self.ollama_base_url = "http://localhost:11434"
        
        # Fallback models (initially Google only)
        self.fallback_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
        
        # Try to find local Ollama models to add to fallback
        try:
            ollama_models = self._fetch_ollama_models()
            if ollama_models:
                logger.info(f"Adding local Ollama models to fallback: {ollama_models}")
                self.fallback_models.extend(ollama_models)
        except Exception as e:
            logger.warning(f"Could not discover local Ollama models: {e}")
        
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            logger.warning("GOOGLE_API_KEY not found. Google LLM features will be disabled.")
            self.client = None
            
        self.model = self.primary_model_name

    def _fetch_ollama_models(self):
        """Helper to get list of local Ollama models"""
        import requests
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=1)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            return []

    def _is_ollama_model(self, model_name: str) -> bool:
        """Check if model is likely an Ollama model"""
        # If it starts with gemini, it's definitely Google
        if model_name.startswith("gemini"):
            return False
            
        # Check known Google-hosted Gemma models
        known_google_models = {
            "gemma-3-1b-it", "gemma-3-4b-it", 
            "gemma-3-12b-it", "gemma-3-27b-it"
        }
        if model_name in known_google_models:
            return False
            
        return True

    def _generate_ollama_content(self, model_name: str, prompt: str) -> str:
        """Generate content using Ollama API"""
        import requests
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")

    def get_available_models(self):
        """Get list of available models from Google and Ollama"""
        models = {
            "google": [
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-3-flash-preview",
                "gemma-3-1b-it",
                "gemma-3-4b-it", 
                "gemma-3-12b-it",
                "gemma-3-27b-it"
            ],
            "ollama": []
        }
        
        # Fetch Ollama models
        import requests
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                models["ollama"] = [m["name"] for m in data.get("models", [])]
        except:
            logger.warning("Could not fetch Ollama models (is Ollama running?)")
            
        return models

    def _call_google_model(self, model_name: str, prompt: str):
        """Helper to call Google model (for threading)"""
        if not self.client:
            raise Exception("Google API key not found")
            
        return self.client.models.generate_content(
            model=model_name,
            contents=prompt
        )

    def generate_content(self, prompt: str) -> any:
        """Generate content with automatic fallback for errors"""
        # Internal helper for response compatibility
        class Response:
            def __init__(self, text):
                self.text = text

        errors = []
        models_to_try = [self.primary_model_name] + self.fallback_models
        
        for model_name in models_to_try:
            if not model_name:
                continue
            
            try:
                logger.info(f"Attempting LLM call with: {model_name}")
                
                if self._is_ollama_model(model_name):
                    text = self._generate_ollama_content(model_name, prompt)
                    return Response(text)
                else:
                    # Wrap Google call in timeout
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._call_google_model, model_name, prompt)
                        response = future.result(timeout=30) # 30s strict timeout
                        return Response(response.text)
                    
            except Exception as e:
                error_str = str(e)
                if isinstance(e, concurrent.futures.TimeoutError):
                    error_str = "Request timed out (30s)"
                    
                errors.append(f"{model_name}: {error_str}")
                logger.warning(f"Model {model_name} failed: {error_str}")
                # Try next model for ANY error (Quota, Model Not Found, Timeout, etc.)
                continue
        
        raise Exception(f"All models failed. Errors: {'; '.join(errors)}")

    def generate_advice(self, truth_packet: TruthPacket, rules: CoachSpeechRules) -> str:
        """Generate coaching advice based on truth packet"""
        # Check if we have ANY capability (client or ollama)
        # We can't easily check for Ollama availability here without making a request, 
        # so we let generate_content handle it via exceptions.
        
        prompt = self._construct_prompt(truth_packet, rules)
        
        try:
            response = self.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating advice: {e}")
            return f"Coach: I'm having trouble thinking right now. (Error: {str(e)[:50]}...)"

    def _construct_prompt(self, packet: TruthPacket, rules: CoachSpeechRules) -> str:
        """Construct prompt from truth packet and rules"""
        return f"""
        You are a chess coach. 
        Situation:
        FEN: {packet.fen}
        Eval: {packet.engine_eval}
        Threats: {packet.opponent_threats}
        
        Rules:
        Must: {rules.must}
        Must Not: {rules.must_not}
        
        Give me a short, punchy piece of advice for the player.
        """
