@echo off
stripe listen --forward-to localhost:8000/api/webhooks/stripe
pause
