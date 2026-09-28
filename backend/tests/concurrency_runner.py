"""Real cross-channel inventory race test.

Requires a running API and an OPEN sailing/cabin. Set:
BASE_URL=http://localhost:8000/api
TRAVELER_TOKEN=<traveler access token>
PARTNER_API_KEY=<active partner API key exposed to the same cruise>
SAILING_ID=<same sailing for both calls>
CABIN_ID=<same cabin for both calls>
PARTNER_CUSTOMER_NAME=Test Customer
PARTNER_CUSTOMER_EMAIL=test@example.com
PARTNER_CUSTOMER_PHONE=9999999999 (optional)

The two requests are started together. Exactly one must win the central
cabin_inventory lock; the loser must receive HTTP 409 CABIN_UNAVAILABLE.
"""
import asyncio, os, uuid, httpx
from datetime import date

BASE=os.getenv('BASE_URL','http://localhost:8000/api').rstrip('/')
T=os.environ['TRAVELER_TOKEN']; K=os.environ['PARTNER_API_KEY']; S=os.environ['SAILING_ID']; C=os.environ['CABIN_ID']
NAME=os.getenv('PARTNER_CUSTOMER_NAME','Concurrency Test Customer'); EMAIL=os.getenv('PARTNER_CUSTOMER_EMAIL','concurrency@example.com')

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        traveler_headers={'Authorization':f'Bearer {T}','Idempotency-Key':f'concurrency-{uuid.uuid4()}'}
        partner_headers={'X-Partner-API-Key':K,'Idempotency-Key':f'concurrency-partner-{uuid.uuid4()}'}
        direct_payload={'sailing_id':S,'cabins':[{'cabin_id':C,'occupancy':1}],'guests':[]}
        partner_payload={'sailing_id':S,'cabins':[{'cabin_id':C,'occupancy':1}],'guest_count':1,'customer_name':NAME,'customer_email':EMAIL,'guests':[{'cabin_id':C,'full_name':NAME,'date_of_birth':'1990-01-01','nationality':'IN','is_lead_guest':True}]}
        async def direct(): return await client.post(f'{BASE}/bookings/hold',headers=traveler_headers,json=direct_payload)
        async def partner(): return await client.post(f'{BASE}/partner-api/bookings',headers=partner_headers,json=partner_payload)
        direct_response, partner_response = await asyncio.gather(direct(), partner())
        statuses=(direct_response.status_code, partner_response.status_code)
        print('traveler hold:', statuses[0], direct_response.text)
        print('partner hold:', statuses[1], partner_response.text)
        assert sorted(statuses) == [200,409], f'Expected exactly one success and one conflict, got {statuses}'

if __name__=='__main__': asyncio.run(main())
