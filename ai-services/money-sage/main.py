# main.py
import os
import sys
import logging
from typing import List, Optional, Dict, Any
from datetime import date, timedelta, timezone, datetime
from collections import defaultdict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, UUID4
from sqlalchemy.exc import SQLAlchemyError
import google.generativeai as genai

from auth import get_current_user_claims
from db import MoneyDb

load_dotenv()

# --- Logging & Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "money-sage", "message": "%(message)s"}',
    stream=sys.stdout,
)
AI_META_DB_URI = os.getenv("AI_META_DB_URI")
BALANCE_READER_URL = os.getenv("BALANCE_READER_URL")
TRANSACTION_HISTORY_URL = os.getenv("TRANSACTION_HISTORY_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini if API key is available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logging.info("Gemini API configured successfully")
else:
    logging.warning("GEMINI_API_KEY not set. AI-powered tips will use fallback logic.")

# --- Pydantic Data Models ---
class BudgetBase(BaseModel):
    category: str
    budget_limit: float  # Input in dollars

class BudgetCreate(BudgetBase):
    period_start: date
    period_end: date

class Budget(BudgetBase):
    id: UUID4
    account_id: str
    period_start: date
    period_end: date
    spent: Optional[float] = 0  # Spent amount in dollars

class BudgetUpdate(BaseModel):
    category: Optional[str] = None
    budget_limit: Optional[float] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Money-Sage",
    version="1.3.1", 
    description="An intelligent financial management service."
)

# --- Global Clients ---
client = httpx.AsyncClient()
db = MoneyDb(AI_META_DB_URI, logging)

# --- API Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "money-sage"}

@app.get("/balance/{account_id}")
async def get_balance(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims), authorization: Optional[str] = Header(None)):
    headers = {"Authorization": authorization} if authorization else {}
    try:
        url = f"{BALANCE_READER_URL}/balances/{account_id}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        # Core returns cents; present dollars to user
        cents = resp.json()
        try:
            dollars = round((int(cents) / 100.0), 2)
        except Exception:
            dollars = cents
        return {"balance": dollars}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/transactions/{account_id}")
async def get_transactions(
    account_id: str, 
    limit: int = 5,
    order: str = "desc",  # 'desc' for newest first (default), 'asc' for oldest first
    transaction_type: Optional[str] = None,  # Filter: 'debit', 'credit', or None for both
    anomaly_status: Optional[str] = None,     # Filter: 'normal', 'suspicious', 'fraud', or None for all
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """
    Get transaction logs from ai-meta-db.
    Returns categorized transactions with amounts, types (debit/credit), and anomaly information.
    
    Args:
        account_id: User's account ID
        limit: Maximum number of transactions to return (default: 5, returns all available if less than limit)
        order: Sort order - 'desc' for newest first (default), 'asc' for oldest first
        transaction_type: Optional filter - 'debit' for sent money, 'credit' for received money
        anomaly_status: Optional filter - 'normal', 'suspicious', or 'fraud'
    """
    try:
        # Validate order parameter
        if order not in ["asc", "desc"]:
            order = "desc"
        
        transactions = db.get_transaction_logs(
            account_id, 
            limit=limit, 
            order=order,
            transaction_type=transaction_type, 
            anomaly_status=anomaly_status
        )
        
        # Convert amounts from cents to dollars for display
        for txn in transactions:
            if 'amount' in txn and txn['amount'] is not None:
                txn['amount_dollars'] = round(txn['amount'] / 100.0, 2)
        
        return {
            "account_id": account_id,
            "count": len(transactions),
            "limit": limit,
            "order": order,
            "filters": {
                "transaction_type": transaction_type,
                "anomaly_status": anomaly_status
            },
            "transactions": transactions
        }
    except SQLAlchemyError as e:
        logging.error(f"Database error fetching transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/transactions/{account_id}/count")
async def get_transaction_count(
    account_id: str,
    transaction_type: Optional[str] = None,
    anomaly_status: Optional[str] = None,
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """
    Get total count of transactions for an account.
    
    Args:
        account_id: User's account ID
        transaction_type: Optional filter - 'debit' or 'credit'
        anomaly_status: Optional filter - 'normal', 'suspicious', 'fraud'
    """
    try:
        total_count = db.get_transaction_count(
            account_id,
            transaction_type=transaction_type,
            anomaly_status=anomaly_status
        )
        return {
            "account_id": account_id,
            "total_count": total_count,
            "filters": {
                "transaction_type": transaction_type,
                "anomaly_status": anomaly_status
            }
        }
    except SQLAlchemyError as e:
        logging.error(f"Database error fetching transaction count: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.post("/budgets/{account_id}", response_model=Budget)
async def create_budget(account_id: str, budget: BudgetCreate, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        # Convert dollars to cents for DB storage
        budget_limit_cents = int(round(budget.budget_limit * 100))
        budget_for_db = budget.model_copy(update={'budget_limit': budget_limit_cents})
        
        new_budget_row = db.create_budget(account_id, budget_for_db)
        if not new_budget_row:
            raise HTTPException(status_code=500, detail="Failed to create budget.")
        
        # Convert back to dollars for response
        result = dict(new_budget_row._mapping)
        result['budget_limit'] = round(result['budget_limit'] / 100.0, 2)
        return result
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/budgets/{account_id}", response_model=List[Budget])
async def get_budgets(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        budgets = db.get_budgets(account_id)
        
        # Calculate spent amounts for each budget from budget_usage
        today = datetime.now(timezone.utc).date()
        
        budgets_with_spent = []
        for budget in budgets:
            period_start = budget.get('period_start', today.replace(day=1))
            period_end = budget.get('period_end', (today.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1))
            
            # Get spending for this category in the budget period
            spending_by_category = db.get_budget_usage(account_id, period_start, period_end)
            spent_cents = spending_by_category.get(budget['category'], 0)
            
            budget_with_spent = dict(budget)
            # Convert to dollars
            budget_with_spent['budget_limit'] = round(budget['budget_limit'] / 100.0, 2)
            budget_with_spent['spent'] = round(spent_cents / 100.0, 2)
            budgets_with_spent.append(budget_with_spent)
        
        return budgets_with_spent
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.put("/budgets/{account_id}/{category}", response_model=Budget)
async def update_budget(account_id: str, category: str, budget_update: BudgetUpdate, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    update_data = budget_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided.")
    
    # Convert dollars to cents for DB
    if 'budget_limit' in update_data:
        update_data['budget_limit'] = int(round(update_data['budget_limit'] * 100))

    try:
        updated_count = db.update_budget(account_id, category, update_data)
        if updated_count == 0:
            raise HTTPException(status_code=404, detail=f"Budget for category '{category}' not found.")
        
        # Fetch the updated budget and include the current spent amount
        budgets = db.get_budgets(account_id)
        updated_budget = next((b for b in budgets if b['category'] == category), None)
        
        if updated_budget:
            today = datetime.now(timezone.utc).date()
            period_start = updated_budget.get('period_start', today.replace(day=1))
            period_end = updated_budget.get('period_end', (today.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1))
            
            spending_by_category = db.get_budget_usage(account_id, period_start, period_end)
            spent_cents = spending_by_category.get(category, 0)
            
            updated_budget = dict(updated_budget)
            # Convert to dollars
            updated_budget['budget_limit'] = round(updated_budget['budget_limit'] / 100.0, 2)
            updated_budget['spent'] = round(spent_cents / 100.0, 2)
            
        return updated_budget
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.delete("/budgets/{account_id}/{category}")
async def delete_budget(account_id: str, category: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        deleted_count = db.delete_budget(account_id, category)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Budget for category '{category}' not found.")
        return {"status": "deleted", "category": category}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/summary/{account_id}")
async def get_summary(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        today = datetime.now(timezone.utc).date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        
        spending_summary = db.get_budget_usage(account_id, start_of_month, end_of_month)
        return {"account_id": account_id, "spending_by_category": spending_summary}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/overview/{account_id}")
async def get_overview(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    try:
        budgets = db.get_budgets(account_id)
        if not budgets:
            return {"account_id": account_id, "overview": {}, "message": "No budgets created yet."}

        today = datetime.now(timezone.utc).date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        
        spending_by_category = db.get_budget_usage(account_id, start_of_month, end_of_month)
        
        overview = {}
        for b in budgets:
            # Filter out expired or future budgets
            b_end = b.get('period_end')
            b_start = b.get('period_start')
            
            # Ensure we have date objects (handle strings if necessary)
            if isinstance(b_end, str):
                try: b_end = datetime.strptime(b_end, "%Y-%m-%d").date()
                except: pass
            if isinstance(b_start, str):
                try: b_start = datetime.strptime(b_start, "%Y-%m-%d").date()
                except: pass

            # Skip if budget is expired or in future
            if b_end and b_end < today:
                continue
            if b_start and b_start > today:
                continue

            category = b['category']
            # If multiple active budgets for same category exist (edge case),
            # this logic might overwrite. Ideally, we sum limits or pick the most recent.
            # But the primary fix requested is filtering expired ones.
            
            spent_cents = spending_by_category.get(category, 0)
            limit_cents = b['budget_limit']

            # Convert to Dollars
            spent = round(spent_cents / 100.0, 2)
            limit = round(limit_cents / 100.0, 2)

            remaining = limit - spent
            status = "on_track"
            if spent > limit:
                status = "over_budget"
            elif limit > 0 and (spent / limit > 0.8):
                status = "at_risk"

            overview[category] = {
                "limit": limit, "spent": spent,
                "remaining": round(remaining, 2), "status": status,
            }
        return {"account_id": account_id, "overview": overview}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/tips/{account_id}")
async def get_saving_tips(account_id: str, claims: Dict[str, Any] = Depends(get_current_user_claims)):
    """Generate personalized saving tips using AI based on transaction logs and budgets."""
    tips = []
    try:
        # Get budget overview
        overview_data = await get_overview(account_id, claims)
        overview = overview_data.get("overview", {})
        
        # Get transaction logs for detailed spending analysis
        # Only use executed transactions (normal or confirmed, excluding blocked fraud attempts)
        all_logs = db.get_transaction_logs(account_id, limit=50)
        transaction_logs = [
            txn for txn in all_logs 
            if txn.get("transaction_id") is not None and 
            txn.get("anomaly_status") in [None, 'normal', 'confirmed']
        ][:20]
        
        # Prepare context for AI
        if GEMINI_API_KEY and (overview or transaction_logs):
            # Aggregate spending by category from transaction logs
            spending_by_category = {}
            transaction_count_by_category = {}
            
            for txn in transaction_logs:
                category = txn.get("category", "Miscellaneous")
                amount = txn.get("amount", 0) / 100.0  # Convert cents to dollars
                
                if category in spending_by_category:
                    spending_by_category[category] += amount
                    transaction_count_by_category[category] += 1
                else:
                    spending_by_category[category] = amount
                    transaction_count_by_category[category] = 1
            
            # Call Gemini for personalized tips
            try:
                model = genai.GenerativeModel('models/gemini-2.5-flash')
                
                prompt = f"""You are a helpful financial advisor for a banking app. Based on the user's transaction history and budgets, provide 3-5 personalized, actionable saving tips.

Transaction History Analysis (Last {len(transaction_logs)} transactions):
{format_transaction_analysis(spending_by_category, transaction_count_by_category)}

Budget Overview:
{format_budget_context(overview)}

Guidelines:
1. Be specific and actionable - reference actual categories and amounts
2. Provide realistic suggestions based on spending patterns
3. Be encouraging and positive in tone
4. Focus on categories with highest spending or budget concerns
5. Keep each tip to 1-2 sentences
6. Include specific dollar amounts when relevant

Return ONLY a JSON array of tip strings, nothing else. Example format:
["Tip 1 text here", "Tip 2 text here", "Tip 3 text here"]"""

                response = model.generate_content(prompt)
                
                # Try to parse JSON response
                import json
                try:
                    # Try to extract JSON from response
                    response_text = response.text.strip()
                    # Remove markdown code blocks if present
                    if response_text.startswith('```'):
                        response_text = response_text.split('```')[1]
                        if response_text.startswith('json'):
                            response_text = response_text[4:]
                        response_text = response_text.strip()
                    
                    tips = json.loads(response_text)
                    if not isinstance(tips, list):
                        tips = [response.text]
                except json.JSONDecodeError:
                    # If not valid JSON, split by newlines and clean
                    tips = [line.strip() for line in response.text.split('\n') if line.strip()]
                    # Remove list markers and quotes
                    tips = [tip.strip('- ').strip('"').strip('•').strip() for tip in tips if tip and not tip.strip() in ['[', ']', '```', '```json']]
                
                # Filter out empty tips
                tips = [tip for tip in tips if tip and len(tip) > 10]
                
            except Exception as e:
                logging.error(f"Error generating AI tips: {e}")
                # Fallback to rule-based tips
                tips = generate_rule_based_tips(overview, spending_by_category)
        else:
            # Fallback to rule-based tips
            spending_by_category = {}
            for txn in transaction_logs:
                category = txn.get("category", "Miscellaneous")
                amount = txn.get("amount", 0) / 100.0
                spending_by_category[category] = spending_by_category.get(category, 0) + amount
            
            tips = generate_rule_based_tips(overview, spending_by_category)
        
        if not tips:
            tips.append("You're doing a great job managing your finances! Keep tracking your spending to find more ways to save.")
        
        return {"account_id": account_id, "tips": tips[:5]}  # Limit to 5 tips
    except Exception as e:
        logging.error(f"Error generating tips: {e}")
        return {
            "account_id": account_id, 
            "tips": ["Unable to generate tips at this time. Please check your budget settings and transaction history."]
        }

def format_transaction_analysis(spending_by_category: dict, transaction_count: dict) -> str:
    """Format transaction spending analysis for AI prompt."""
    if not spending_by_category:
        return "No recent transactions found"
    
    lines = []
    # Sort by spending amount (highest first)
    sorted_spending = sorted(spending_by_category.items(), key=lambda x: x[1], reverse=True)
    
    for category, amount in sorted_spending:
        count = transaction_count.get(category, 0)
        avg_per_transaction = amount / count if count > 0 else 0
        lines.append(f"- {category}: ${amount:.2f} total ({count} transactions, avg ${avg_per_transaction:.2f} per transaction)")
    
    return "\n".join(lines)

def format_budget_context(overview: dict) -> str:
    """Format budget overview for AI prompt."""
    if not overview:
        return "No budgets set"
    
    lines = []
    for category, data in overview.items():
        limit = data.get("limit", 0)
        spent = data.get("spent", 0)
        remaining = data.get("remaining", 0)
        status = data.get("status", "unknown")
        percentage = (spent / limit * 100) if limit > 0 else 0
        lines.append(f"- {category}: ${spent:.2f} / ${limit} ({percentage:.0f}% used, {status})")
    return "\n".join(lines)

def generate_rule_based_tips(overview: dict, spending_by_category: dict = None) -> List[str]:
    """Generate rule-based tips as fallback when AI is not available."""
    import random
    tips = []
    
    # Expanded tip templates for variety
    over_budget_templates = [
        "You've exceeded your {category} budget by ${amount:.2f}. Consider reviewing your spending in this area.",
        "Your {category} spending is ${amount:.2f} over budget. Look for ways to cut back this month.",
        "Alert: {category} is ${amount:.2f} over the limit. Try the envelope method to stay on track.",
        "Budget exceeded in {category} by ${amount:.2f}. Consider meal prepping or finding free alternatives.",
    ]
    
    at_risk_templates = [
        "You've used {percentage:.0f}% of your {category} budget. Slow down spending to avoid going over.",
        "{category} is at {percentage:.0f}% used - only ${remaining:.2f} left. Plan carefully!",
        "Warning: {category} budget is {percentage:.0f}% spent with ${remaining:.2f} remaining.",
        "Almost there! {category} is at {percentage:.0f}%. Consider delaying non-essential purchases.",
    ]
    
    on_track_templates = [
        "Great job staying within your {category} budget at {percentage:.0f}% used!",
        "You're doing well with {category} - only {percentage:.0f}% spent so far.",
        "{category} budget is on track ({percentage:.0f}% used). Keep it up!",
    ]
    
    general_tips = [
        "Try the 50/30/20 rule: 50% needs, 30% wants, 20% savings.",
        "Review subscriptions monthly - cancel unused ones to save money.",
        "Set up automatic transfers to savings right after payday.",
        "Use cashback apps and credit card rewards for everyday purchases.",
        "Plan meals weekly to reduce food waste and save on groceries.",
        "Wait 24-48 hours before making non-essential purchases over $50.",
        "Track every expense for a week to identify spending patterns.",
        "Consider no-spend days or weeks to boost your savings.",
        "Shop with a list and avoid impulse buying.",
        "Compare prices online before making major purchases.",
        "Negotiate bills like internet and insurance annually.",
        "Build an emergency fund of 3-6 months of expenses.",
    ]
    
    # Tips based on budget overview
    for category, data in overview.items():
        status = data.get("status")
        spent = data.get("spent", 0)
        limit = data.get("limit", 0)
        remaining = data.get("remaining", 0)
        percentage = (spent / limit * 100) if limit > 0 else 0
        
        if status == "over_budget":
            template = random.choice(over_budget_templates)
            tips.append(template.format(category=category, amount=abs(remaining), percentage=percentage, remaining=remaining))
        elif status == "at_risk":
            template = random.choice(at_risk_templates)
            tips.append(template.format(category=category, amount=abs(remaining), percentage=percentage, remaining=remaining))
        elif status == "on_track" and random.random() > 0.5:  # 50% chance to include positive feedback
            template = random.choice(on_track_templates)
            tips.append(template.format(category=category, amount=spent, percentage=percentage, remaining=remaining))
    
    # Tips based on spending patterns
    if spending_by_category:
        sorted_spending = sorted(spending_by_category.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_spending) > 0:
            top_category, top_amount = sorted_spending[0]
            spending_tips = [
                f"Your highest spending is {top_category} (${top_amount:.2f}). Set a budget to track it better.",
                f"{top_category} leads your spending at ${top_amount:.2f}. Look for ways to reduce costs here.",
                f"Focus on {top_category} (${top_amount:.2f}) - your biggest expense category.",
            ]
            if top_amount > 100:
                tips.append(random.choice(spending_tips))
        
        # Second highest category tip
        if len(sorted_spending) > 1:
            second_category, second_amount = sorted_spending[1]
            if second_amount > 50 and random.random() > 0.6:
                tips.append(f"Also watch {second_category} spending (${second_amount:.2f}) - your second largest category.")
    
    # Add general tips to fill up to 3-5 tips
    random.shuffle(general_tips)
    while len(tips) < 3:
        if general_tips:
            tips.append(general_tips.pop())
        else:
            break
    
    # Shuffle the final list for variety
    random.shuffle(tips)
    
    return tips[:5]  # Return max 5 tips