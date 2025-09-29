# Author: Dhaval Patel. Codebasics YouTube Channel (modified & fixed)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helper
import generic_helper

app = FastAPI()

# Keep track of in-progress orders per session
inprogress_orders = {}


@app.post("/")
async def handle_request(request: Request):
    payload = await request.json()

    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult'].get('outputContexts', [])

    # Extract session_id safely
    session_id = ""
    if output_contexts:
        session_id = generic_helper.extract_session_id(output_contexts[0]["name"])

    # Map Dialogflow intents to Python handlers
    intent_handler_dict = {
        'new.order': new_order,
        'order.add.items - context:ongoing order': add_to_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order': track_order,
        'track.order - context: ongoing-tracking': track_order
    }

    if intent in intent_handler_dict:
        return intent_handler_dict[intent](parameters, session_id)
    else:
        return JSONResponse(content={
            "fulfillmentText": f"Sorry, I don't know how to handle the intent '{intent}'."
        })


# ---------------------------
# Helpers
# ---------------------------

def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()
    for food_item, quantity in order.items():
        rcode = db_helper.insert_order_item(food_item, quantity, next_order_id)
        if rcode == -1:
            return -1

    db_helper.insert_order_tracking(next_order_id, "in progress")
    return next_order_id


# ---------------------------
# Intent Handlers
# ---------------------------

def new_order(parameters: dict, session_id: str):
    inprogress_orders[session_id] = {}
    return JSONResponse(content={
        "fulfillmentText": "What would you like to order?"
    })


def add_to_order(parameters: dict, session_id: str):
    food_items = parameters.get("food", [])
    quantities = parameters.get("number", [])

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry, I didn't understand. Please specify items and quantities clearly."
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_orders:
            current_food_dict = inprogress_orders[session_id]
            current_food_dict.update(new_food_dict)
            inprogress_orders[session_id] = current_food_dict
        else:
            inprogress_orders[session_id] = new_food_dict

        order_str = generic_helper.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "I can't find your order. Can you start a new one?"
        })

    food_items = parameters.get("food", [])
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item in current_order:
            removed_items.append(item)
            del current_order[item]
        else:
            no_such_items.append(item)

    fulfillment_text = ""
    if removed_items:
        fulfillment_text += f"Removed {', '.join(removed_items)} from your order. "
    if no_such_items:
        fulfillment_text += f"Your order does not contain {', '.join(no_such_items)}. "

    if not current_order:
        fulfillment_text += "Your order is now empty."
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f"Remaining items: {order_str}."

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I can't find your order. Can you place a new one?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)
        if order_id == -1:
            fulfillment_text = "Sorry, there was an error. Please try again."
        else:
            order_total = db_helper.get_total_order_price(order_id)
            fulfillment_text = (
                f"Order placed! Your order id is #{order_id}. "
                f"Total = {order_total:.2f}. Please pay on delivery."
            )
        del inprogress_orders[session_id]

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def track_order(parameters: dict, session_id: str):
    order_id = None

    # Check both possible parameter names
    if "order_id" in parameters:
        order_id = parameters.get("order_id")
    elif "number" in parameters and parameters["number"]:
        order_id = parameters["number"][0]

    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return JSONResponse(content={
            "fulfillmentText": "Please provide a valid order ID to track your order."
        })

    order_status = db_helper.get_order_status(order_id)
    if order_status:
        fulfillment_text = f"The status of order #{order_id} is: {order_status}."
    else:
        fulfillment_text = f"No order found with ID #{order_id}."

    return JSONResponse(content={"fulfillmentText": fulfillment_text})
