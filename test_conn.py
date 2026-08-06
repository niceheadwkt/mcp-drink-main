
import db_logic
import logging

logging.basicConfig(level=logging.INFO)

def test():
    print("Testing Firestore connection...")
    orders = db_logic.fetch_cloud_orders()
    if orders is not None:
        print(f"Successfully connected! Found {len(orders)} orders.")
        if len(orders) > 0:
            print("First order sample:")
            print(orders[0])
    else:
        print("Failed to connect to Firestore.")

if __name__ == "__main__":
    test()
