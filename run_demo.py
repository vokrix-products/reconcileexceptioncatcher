from processor import process_file

def main():
    test_bytes = b"supplier,product,price\nAcme,Widget,9.99\nBeta,Gadget,12.50\nAcme,Widget,9.99\nGamma,Gizmo,no_price\n"
    results = process_file(test_bytes)
    assert isinstance(results, list)
    print(f"Processed {len(results)} records")
    for rec in results:
        print(f"Title: {rec['title']}, Status: {rec['status']}, Due Date: {rec['due_date']}")
    print("Demo completed successfully.")

if __name__ == "__main__":
    main()
