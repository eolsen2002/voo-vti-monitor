# test_tos_api.py
from voo_vti_fetcher import get_voo_vti_quotes

print("Testing Schwab API…")

result = get_voo_vti_quotes()

if result:
    print("API result:")
    print(result)
else:
    print("No data returned.")