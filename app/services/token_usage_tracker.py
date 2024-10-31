from pymongo import MongoClient, UpdateOne
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timedelta
from typing import Dict, Optional, Union, Tuple, List
import logging
import os
from dotenv import load_dotenv
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenUsageTracker:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.database_name = "kyndom"
        self.client = None

    async def connect(self):
        """Establish MongoDB connection"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.database_name]
            # Test connection
            self.client.admin.command('ismaster')
            logger.info("Successfully connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    def _calculate_period_dates(self, subscription: Dict) -> Tuple[datetime, datetime]:
        """Calculate current billing period start and end dates"""
        now = datetime.now()
        
        if subscription['tariff'] == 'MONTHLY_PLAN':
            # For monthly plans, period starts on subscription start date and extends for a month
            period_start = subscription.get('createdAt')
            while period_start + timedelta(days=30) < now:
                period_start += timedelta(days=30)
            period_end = period_start + timedelta(days=30)
        else:  # YEARLY_PLAN
            # For yearly plans, period starts on subscription start date and extends for a year
            period_start = subscription.get('createdAt')
            while period_start + timedelta(days=365) < now:
                period_start += timedelta(days=365)
            period_end = period_start + timedelta(days=365)
            
        return period_start, period_end
    
    def _calculate_tokens_from_metrics(self, metrics: Dict) -> Dict[str, int]:
        """Calculate token totals from metrics response"""
        try:
            if metrics is None:
                logger.error("Metrics dictionary is None")
                return {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0
                }

            # Convert defaultdict values to regular values if needed
            input_tokens = metrics.get('input_tokens', [])
            output_tokens = metrics.get('output_tokens', [])
            total_tokens = metrics.get('total_tokens', [])

            # Handle both single metrics and aggregated metrics formats
            if isinstance(input_tokens, list):
                return {
                    'input_tokens': sum(input_tokens) if input_tokens else 0,
                    'output_tokens': sum(output_tokens) if output_tokens else 0,
                    'total_tokens': sum(total_tokens) if total_tokens else 0
                }
            else:
                return {
                    'input_tokens': input_tokens or 0,
                    'output_tokens': output_tokens or 0,
                    'total_tokens': total_tokens or 0
                }
        except Exception as e:
            logger.error(f"Error calculating tokens from metrics: {str(e)}")
            logger.error(f"Metrics content: {metrics}")
            raise ValueError("Invalid metrics format")

    async def get_or_create_billing_period(
        self,
        user_id: str,
        subscription: Dict
    ) -> Optional[Dict]:
        """Get current billing period or create if it doesn't exist"""
        period_start, period_end = self._calculate_period_dates(subscription)
        
        current_period = self.db.BillingPeriodTokenUsage.find_one({
            'userId': ObjectId(user_id),
            'subscriptionId': subscription['_id'],
            'periodStart': {'$lte': datetime.now()},
            'periodEnd': {'$gt': datetime.now()}
        })
        
        if not current_period:
            # Create new billing period
            current_period = {
                'userId': ObjectId(user_id),
                'subscriptionId': subscription['_id'],
                'periodStart': period_start,
                'periodEnd': period_end,
                'inputTokens': 0,
                'outputTokens': 0,
                'totalTokens': 0,
                'planType': subscription['tariff'],
                'createdAt': datetime.now()
            }
            result = self.db.BillingPeriodTokenUsage.insert_one(current_period)
            current_period['_id'] = result.inserted_id
            
        return current_period

    async def update_user_token_usage(
        self,
        user_id: str,
        metrics: Dict,
        session_id: Optional[str] = None
    ) -> Dict[str, Union[bool, str]]:
        """Update user's token usage for the current billing period"""
        try:
            if not metrics:
                return {"success": False, "error": "No metrics available"}
            
            await self.connect()
            
            try:
                user_object_id = ObjectId(user_id)
            except Exception as e:
                logger.error(f"Invalid user_id format: {str(e)}")
                return {"success": False, "error": "Invalid user ID format"}

            # Get user and active subscription
            user = self.db.User.find_one({'_id': user_object_id})
            if not user:
                return {"success": False, "error": "User not found"}

            subscription = await self._get_active_subscription(user_id)
            if not subscription:
                return {"success": False, "error": "No active subscription found"}

            # Calculate token usage
            token_counts = self._calculate_tokens_from_metrics(metrics)
            
            # Get or create current billing period
            current_period = await self.get_or_create_billing_period(user_id, subscription)
            
            try:
                # Update user's running totals
                user_update_result = self.db.User.update_one(
                    {'_id': user_object_id},
                    {
                        '$inc': {
                            'currentPeriodTokens': token_counts['total_tokens'],
                            'totalTokensUsed': token_counts['total_tokens']
                        }
                    }
                )

                # Update billing period totals
                billing_update_result = self.db.BillingPeriodTokenUsage.update_one(
                    {'_id': current_period['_id']},
                    {
                        '$inc': {
                            'inputTokens': token_counts['input_tokens'],
                            'outputTokens': token_counts['output_tokens'],
                            'totalTokens': token_counts['total_tokens']
                        },
                        '$set': {
                            'updatedAt': datetime.now()
                        }
                    }
                )

                if user_update_result.modified_count > 0 and billing_update_result.modified_count > 0:
                    logger.info(f"Updated token usage for user {user_id} in current billing period")
                    return {
                        "success": True,
                        "message": "Token usage updated successfully",
                        "tokens_used": token_counts['total_tokens'],
                        "billing_period_id": str(current_period['_id'])
                    }
                else:
                    logger.error(f"Failed to update token usage for user {user_id}")
                    return {"success": False, "error": "Failed to update token usage"}

            except OperationFailure as e:
                logger.error(f"Database operation failed: {str(e)}")
                return {"success": False, "error": "Database operation failed"}

        except Exception as e:
            logger.error(f"Unexpected error in token usage update: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            await self.close()

    async def _get_active_subscription(self, user_id: str) -> Optional[Dict]:
        """Fetch user's active subscription"""
        try:
            subscription = self.db.Subscription.find_one({
                'userId': ObjectId(user_id),
                'status': 'ACTIVE'
            })
            return subscription
        except Exception as e:
            logger.error(f"Error fetching subscription: {str(e)}")
            return None

    async def get_billing_period_usage(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Retrieve billing period usage history"""
        try:
            await self.connect()
            
            query = {'userId': ObjectId(user_id)}
            if start_date:
                query['periodStart'] = {'$gte': start_date}
            if end_date:
                query['periodEnd'] = {'$lte': end_date}
                
            usage_history = self.db.BillingPeriodTokenUsage.find(
                query,
                sort=[('periodStart', -1)]
            )
            
            return list(usage_history)
            
        except Exception as e:
            logger.error(f"Error retrieving billing period usage: {str(e)}")
            return []
        finally:
            await self.close()