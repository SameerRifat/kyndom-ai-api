from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timedelta
from typing import Dict, Optional, Union, List
from bson.objectid import ObjectId
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TokenUsageTracker:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.database_name = "kyndom"
        self.client = None
        logger.debug(f"TokenUsageTracker initialized with database: {self.database_name}")

    async def connect(self):
        try:
            logger.debug(f"Attempting to connect to MongoDB at {self.mongo_uri[:20]}...")
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.database_name]
            self.client.admin.command('ismaster')
            logger.info("Successfully connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def get_active_subscription(self, user_id: str) -> Optional[Dict]:
        """Get active subscription for a user directly from Subscription collection"""
        try:
            logger.debug(f"Getting active subscription for user_id: {user_id}")
            now = datetime.now()
            
            # Find active subscription
            subscription = self.db.Subscription.find_one({
                'userId': ObjectId(user_id),
                'status': 'ACTIVE',
                'startDate': {'$lte': now},
                'endDate': {'$gt': now}
            })
            
            if not subscription:
                logger.warning(f"No active subscription found for user_id: {user_id}")
                return None
                
            logger.debug(f"Found active subscription: {subscription}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error getting active subscription: {str(e)}", exc_info=True)
            return None

    async def _create_new_usage_period(self, subscription_id: ObjectId) -> Dict:
        """Create a new usage period for a subscription and process any pending usage"""
        logger.debug(f"Creating new usage period for subscription_id: {subscription_id}")
        
        try:
            subscription = self.db.Subscription.find_one({'_id': subscription_id})
            logger.debug(f"Found subscription data: {subscription}")
            
            if not subscription:
                error_msg = f"Subscription not found for ID: {subscription_id}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            now = datetime.now()
            logger.debug(f"Monthly token quota from subscription: {subscription['monthlyBudget']}")

            new_period = {
                'subscriptionId': subscription_id,
                'periodStart': subscription['startDate'],
                'periodEnd': subscription['endDate'],
                'quotaForPeriod': subscription.get('monthlyBudget', 0),
                'totalInputTokensUsed': 0,
                'totalOutputTokensUsed': 0,
                'totalCachedInputTokensUsed': 0,
                'totalCharactersUsed': 0,
                'totalSecondsUsed': 0,
                'createdAt': now,
                'updatedAt': now
            }
            
            logger.debug(f"Attempting to insert new usage period: {new_period}")
            result = self.db.UsagePeriod.insert_one(new_period)
            new_period['_id'] = result.inserted_id
            logger.info(f"Created new usage period with ID: {result.inserted_id}")
            
            return new_period

        except Exception as e:
            logger.error(f"Error creating new usage period: {str(e)}", exc_info=True)
            raise

    async def get_active_usage_period(self, user_id: str) -> Optional[Dict]:
        """Get the current usage period for a user"""
        try:
            logger.debug(f"Getting active usage period for user_id: {user_id}")

            # Get user's active subscription directly from Subscription collection
            active_subscription = await self.get_active_subscription(user_id)
            
            if not active_subscription:
                logger.warning(f"No active subscription found for user_id: {user_id}")
                return None

            # Find current usage period
            logger.debug(f"Looking for usage period for subscription: {active_subscription['_id']}")
            current_period = self.db.UsagePeriod.find_one({
                'subscriptionId': active_subscription['_id'],
                'periodStart': {'$lte': datetime.now()},
                'periodEnd': {'$gt': datetime.now()}
            })
            logger.debug(f"Found usage period: {current_period}")

            if not current_period:
                logger.info("No active usage period found, creating new one...")
                current_period = await self._create_new_usage_period(
                    active_subscription['_id']
                )
                logger.debug(f"Created new usage period: {current_period}")

            return current_period
        except Exception as e:
            logger.error(f"Error getting active usage period: {str(e)}", exc_info=True)
            return None

    def _process_metrics(self, metrics: Dict) -> Dict[str, int]:
        """Process and validate metrics data"""
        logger.debug(f"Processing metrics: {metrics}")
        try:
            # Initialize result dict
            result = {
                'input_tokens': 0,
                'output_tokens': 0,
                'cached_tokens': 0
            }
            
            # Handle list-type metrics (aggregating multiple calls)
            if isinstance(metrics.get('input_tokens'), list):
                result['input_tokens'] = sum(metrics.get('input_tokens', []))
                result['output_tokens'] = sum(metrics.get('output_tokens', []))
                
                # Process cached tokens from prompt_tokens_details
                prompt_details = metrics.get('prompt_tokens_details', [])
                result['cached_tokens'] = sum(
                    detail.get('cached_tokens', 0) 
                    for detail in prompt_details
                    if isinstance(detail, dict)
                )
                
            # Handle scalar metrics (single call)
            else:
                result['input_tokens'] = metrics.get('input_tokens', 0)
                result['output_tokens'] = metrics.get('output_tokens', 0)
                
                # Get cached tokens from prompt_tokens_details if available
                prompt_details = metrics.get('prompt_tokens_details', [])
                if prompt_details and isinstance(prompt_details[0], dict):
                    result['cached_tokens'] = prompt_details[0].get('cached_tokens', 0)
            
            logger.debug(f"Processed metrics: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing metrics: {str(e)}", exc_info=True)
            return {
                'input_tokens': 0, 
                'output_tokens': 0,
                'cached_tokens': 0
            }
        
    async def update_user_token_usage(
        self,
        user_id: str,
        metrics: Dict,
        message_type: str = 'TEXT_CHAT'
    ) -> Dict[str, Union[bool, str]]:
        """Update token usage for a user's message"""
        logger.debug(f"Starting token usage update for user_id: {user_id}")
        logger.debug(f"Incoming metrics: {metrics}")
        logger.debug(f"Message type: {message_type}")
        
        try:
            await self.connect()
            
            # Get active usage period
            logger.debug("Fetching active usage period...")
            usage_period = await self.get_active_usage_period(user_id)

            # If no active usage period, store as pending usage
            if not usage_period:
                return {"success": False, "error": "No active usage period found"}

            # Process metrics
            logger.debug("Processing metrics...")
            token_counts = self._process_metrics(metrics)
            logger.debug(f"Processed token counts: {token_counts}")
            total_tokens = token_counts['input_tokens'] + token_counts['output_tokens']
            logger.info(f"Total tokens to be recorded: {total_tokens}")

            # Create message record
            message = {
                'userId': ObjectId(user_id),
                'usagePeriodId': usage_period['_id'],
                'messageType': message_type,
                'inputTokens': token_counts['input_tokens'],
                'outputTokens': token_counts['output_tokens'],
                'cachedInputTokens': token_counts['cached_tokens'],
                'createdAt': datetime.now()
            }
            logger.debug(f"Preparing to insert message record: {message}")
            
            # Insert message and update usage period
            try:
                message_result = self.db.Message.insert_one(message)
                logger.debug(f"Message inserted with ID: {message_result.inserted_id}")
            except Exception as e:
                logger.error(f"Failed to insert message record: {str(e)}", exc_info=True)
                return {"success": False, "error": "Failed to insert message record"}
            
            try:
                logger.debug(f"Updating usage period {usage_period['_id']} with {total_tokens} tokens")
                update_result = self.db.UsagePeriod.update_one(
                    {'_id': usage_period['_id']},
                    {
                        '$inc': {'totalInputTokensUsed': token_counts['input_tokens'], 'totalOutputTokensUsed': token_counts['output_tokens'], 'totalCachedInputTokensUsed': token_counts['cached_tokens']},
                        '$set': {'updatedAt': datetime.now()}
                    }
                )
                logger.debug(f"Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
            except Exception as e:
                logger.error(f"Failed to update usage period: {str(e)}", exc_info=True)
                return {"success": False, "error": "Failed to update usage period"}

            if update_result.modified_count > 0:
                logger.info(f"Successfully updated token usage. Total tokens: {total_tokens}")
                return {
                    "success": True,
                    "message": "Token usage updated successfully",
                    "tokens_used": total_tokens,
                    "usage_period_id": str(usage_period['_id'])
                }
            
            logger.warning("Update operation completed but no documents were modified")
            return {"success": False, "error": "Failed to update token usage"}

        except Exception as e:
            logger.error(f"Error updating token usage: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            logger.debug("Closing MongoDB connection...")
            await self.close()

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")