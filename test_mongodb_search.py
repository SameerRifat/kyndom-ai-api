import json
from mongodb_search import mongodb_search  # Replace 'your_module' with the actual module name

def test_mongodb_search():
    # Test case 1: Basic search
    query = "Relocation Checklist"
    result = mongodb_search(query)
    parsed_result = json.loads(result)
    print(f"Test case 1 - Basic search for '{query}':")
    print(f"Number of results: {len(parsed_result)}")
    print(f"Results: {json.dumps(parsed_result, indent=2)}\n")

    # Test case 2: Search with specified number of documents
    # query = "social"
    # num_docs = 3
    # result = mongodb_search(query, num_docs)
    # parsed_result = json.loads(result)
    # print(f"Test case 2 - Search for '{query}' with {num_docs} documents:")
    # print(f"Number of results: {len(parsed_result)}")
    # print(f"Results: {json.dumps(parsed_result, indent=2)}\n")

    # # Test case 3: Search for category (exact match, case-insensitive)
    # query = "STORY_TEMPLATES"
    # result = mongodb_search(query)
    # parsed_result = json.loads(result)
    # print(f"Test case 3 - Search for category '{query}':")
    # print(f"Number of results: {len(parsed_result)}")
    # print(f"Results: {json.dumps(parsed_result, indent=2)}\n")

    # # Test case 4: Search for category (partial match, case-insensitive)
    # query = "story"
    # result = mongodb_search(query)
    # parsed_result = json.loads(result)
    # print(f"Test case 4 - Search for partial category '{query}':")
    # print(f"Number of results: {len(parsed_result)}")
    # print(f"Results: {json.dumps(parsed_result, indent=2)}\n")

    # # Test case 5: Search for category (mixed case)
    # query = "SoCiAl_MeDiA"
    # result = mongodb_search(query)
    # parsed_result = json.loads(result)
    # print(f"Test case 5 - Search for mixed case category '{query}':")
    # print(f"Number of results: {len(parsed_result)}")
    # print(f"Results: {json.dumps(parsed_result, indent=2)}\n")

    # Add more test cases as needed

if __name__ == "__main__":
    test_mongodb_search()