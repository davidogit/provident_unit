import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class PaystackAPI:
    base_url = "https://api.paystack.co"
    
    @classmethod
    def _get_headers(cls):
        """Get headers with proper validation"""
        secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
        if not secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not configured in settings")
        
        return {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }
    
    @classmethod
    def verify_transaction(cls, reference):
        """
        Verify a Paystack transaction with comprehensive error handling
        
        Args:
            reference (str): Transaction reference to verify
            
        Returns:
            dict: API response data or error information
        """
        if not reference:
            return {
                "status": False,
                "message": "Transaction reference is required",
                "data": None
            }
        
        try:
            # Validate configuration
            headers = cls._get_headers()
            if not cls.base_url:
                raise ValueError("Base URL is not configured")
            
            # Construct URL
            url = f"{cls.base_url}/transaction/verify/{reference}"
            
            # Make the request with timeout
            response = requests.get(
                url, 
                headers=headers,
                timeout=30  # 30 second timeout
            )
            
            # Raise an exception for bad status codes
            response.raise_for_status()
            
            # Parse JSON response
            try:
                return response.json()
            except ValueError as json_error:
                logger.error(f"Invalid JSON response from Paystack: {json_error}")
                return {
                    "status": False,
                    "message": "Invalid response format from payment gateway",
                    "data": None
                }
                
        except ValueError as config_error:
            logger.error(f"Configuration error: {config_error}")
            return {
                "status": False,
                "message": "Payment gateway configuration error",
                "data": None
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout verifying transaction {reference}")
            return {
                "status": False,
                "message": "Request timeout - please try again",
                "data": None
            }
            
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error verifying transaction {reference}")
            return {
                "status": False,
                "message": "Unable to connect to payment gateway",
                "data": None
            }
            
        except requests.exceptions.HTTPError as http_error:
            logger.error(f"HTTP error verifying transaction {reference}: {http_error}")
            return {
                "status": False,
                "message": f"Payment gateway error: {http_error.response.status_code}",
                "data": None
            }
            
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Request error verifying transaction {reference}: {req_error}")
            return {
                "status": False,
                "message": "Payment verification failed",
                "data": None
            }
            
        except Exception as unexpected_error:
            logger.error(f"Unexpected error verifying transaction {reference}: {unexpected_error}")
            return {
                "status": False,
                "message": "An unexpected error occurred",
                "data": None
            }