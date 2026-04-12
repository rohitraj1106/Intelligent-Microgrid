"""
strategic_agent/rate_limiter.py
==============================
Senior-grade Token Bucket Rate Limiter for LLM API protection.
Ensures we stay within Gemini/Groq free tier quotas (Requests Per Minute/Day).
"""
import time
import threading
import logging
from collections import deque

logger = logging.getLogger("StrategicAgent.RateLimiter")

class RateLimiter:
    """
    Thread-safe sliding window rate limiter.
    """
    def __init__(self, max_rpm: int = 14):
        self.max_rpm = max_rpm
        self.requests = deque()
        self._lock = threading.Lock()
        
    def await_permit(self):
        """
        Blocks until a request slot is available. Non-blocking to other threads.
        """
        while True:
            sleep_time = 0
            with self._lock:
                now = time.time()
                
                # Cleanup old timestamps
                while self.requests and self.requests[0] < now - 60:
                    self.requests.popleft()
                
                if len(self.requests) < self.max_rpm:
                    self.requests.append(now)
                    return
                
                # Calculate sleep time if window is full
                sleep_time = self.requests[0] + 60.1 - now
            
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Throttling focus node for {sleep_time:.2f}s...")
                time.sleep(sleep_time)

    def get_usage(self) -> int:
        with self._lock:
            now = time.time()
            return len([t for t in self.requests if t > now - 60])
