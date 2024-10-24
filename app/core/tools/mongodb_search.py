from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import json
from bson.json_util import dumps
from dotenv import load_dotenv
import os
import re
import logging

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mongodb_search(query: str, num_documents: int = 5) -> str:
    """Use this function to fetch Kyndom data from multiple interconnected collections in MongoDB based on the search query.

    Args:
        query (str): The search query string for the regex search.
        num_documents (int): The number of documents to return. Defaults to 5.

    Returns:
        str: JSON string of combined search results with associated data.
    """
    # MongoDB connection details from environment variables
    mongo_uri = os.getenv("MONGODB_URI")
    database_name = "kyndom"

    logger.info(f"mongodb_search called with query: {query}")

    client = None
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[database_name]

        # Test the connection
        client.admin.command('ismaster')

        # case-insensitive regex pattern
        # regex_pattern = re.compile(query, re.IGNORECASE)

        def create_flexible_regex(query):
            words = query.split()
            escaped_words = [re.escape(word) for word in words]
            return re.compile('.*'.join(escaped_words), re.IGNORECASE)

        # In the mongodb_search function:
        regex_pattern = create_flexible_regex(query)

        # New function to create a case-insensitive regex for exact category matching
        def create_category_regex(query):
            return re.compile(f"^{re.escape(query)}$", re.IGNORECASE)

        category_pattern = create_category_regex(query)

    # pipelines for different collections
        pipelines = {
        "SocialContentTemplate": [
            {
                "$match": {
                    "$or": [
                        {"title": {"$regex": regex_pattern}},
                        {"commentsText": {"$regex": regex_pattern}},
                        {"hashtagText": {"$regex": regex_pattern}},
                        {"category": {"$regex": category_pattern}},
                    ]
                }
            },
            {
                "$lookup": {
                    "from": "SocialContentTemplateImage",
                    "localField": "_id",
                    "foreignField": "socialContentTemplateId",
                    "as": "images"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "commentsText": 1,
                    "hashtagText": 1,
                    "canvaUrl": 1,
                    "image": {"$arrayElemAt": ["$images.resourceUrl", 0]},
                }
            }
        ],
        "SocialTextTemplate": [
            {
                "$match": {
                    "$or": [
                        {"title": {"$regex": regex_pattern}},
                        {"content": {"$regex": regex_pattern}}
                    ]
                }
            },
            {
                "$project": {
                    "title": 1,
                    "content": 1,
                    "_id": 0
                }
            }
        ],
        "SocialStrategy": [
            {
                "$match": {
                    "$or": [
                        {"title": {"$regex": regex_pattern}},
                        {"content": {"$regex": regex_pattern}},
                        {"type": {"$regex": regex_pattern}}
                    ]
                }
            },
            {
                "$project": {
                    "title": 1,
                    "content": 1,
                    "_id": 0
                }
            }
        ]
    }

    # List of collections to search
        collections_to_search = ["SocialContentTemplate", "SocialTextTemplate", "SocialStrategy"]

        # Aggregate results from all collections
        all_results = []
        for collection_name in collections_to_search:
            pipeline = pipelines.get(collection_name, [])
            try:
                results = list(db[collection_name].aggregate(pipeline))
                all_results.extend(results)
            except OperationFailure as e:
                logger.error(f"Error aggregating data from {collection_name}: {str(e)}")

        # For now, we'll just shuffle the results
        import random
        random.shuffle(all_results)

        # Limit the number of documents returned
        all_results = all_results[:num_documents]

        logger.info(f"Number of results found: {len(all_results)}")

        # Convert the results to JSON format
        return json.dumps(all_results)

    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        return json.dumps({"error": "Database connection failed"})
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return json.dumps({"error": "An unexpected error occurred"})
    finally:
        if client:
            client.close()
            logger.info("MongoDB connection closed")

exports = mongodb_search