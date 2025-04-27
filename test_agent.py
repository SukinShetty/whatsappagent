from src.langgraph_whatsapp.tools import save_link, retrieve_links, set_reminder, extract_links

# Test user ID
user_id = "whatsapp:+1234567890"

# Test save_link
def test_save_link():
    link = "https://example.com"
    result = save_link(user_id, link)
    print(f"Save link result: {result}")

# Test retrieve_links
def test_retrieve_links():
    result = retrieve_links(user_id)
    print(f"Retrieve links result: {result}")

# Test set_reminder
def test_set_reminder():
    time_str = "tomorrow at 3pm"
    task = "call John"
    result = set_reminder(user_id, time_str, task)
    print(f"Set reminder result: {result}")

# Test extract_links
def test_extract_links():
    message = "Check out this article: https://example.com and also this one: https://github.com"
    links = extract_links(message)
    print(f"Extracted links: {links}")

# Run the tests
if __name__ == "__main__":
    print("Testing save_link...")
    test_save_link()
    
    print("\nTesting retrieve_links...")
    test_retrieve_links()
    
    print("\nTesting extract_links...")
    test_extract_links()
    
    print("\nTesting set_reminder...")
    test_set_reminder() 