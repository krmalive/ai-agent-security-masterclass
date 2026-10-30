from agents import function_tool

# FAQ database with questions and answers
FAQ_DB = {
    "shipping": {
        "question": "What are your shipping options?",
        "answer": "We offer free standard shipping (5-7 business days) on orders over $50. Express shipping (2-3 business days) costs $9.99, and overnight shipping is available for $24.99."
    },
    "returns": {
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days of purchase for a full refund. Items must be in original condition with tags attached. Free return shipping labels are provided for defective items."
    },
    "warranty": {
        "question": "Do products come with a warranty?",
        "answer": "All electronics come with a 1-year manufacturer warranty. Extended warranty plans (2 or 3 years) are available at checkout for an additional fee."
    },
    "payment": {
        "question": "What payment methods do you accept?",
        "answer": "We accept all major credit cards (Visa, MasterCard, Amex), PayPal, Apple Pay, Google Pay, and buy-now-pay-later options through Affirm and Klarna."
    },
    "tracking": {
        "question": "How can I track my order?",
        "answer": "Once your order ships, you'll receive a tracking number via email. You can also track your order by logging into your account and visiting 'Order History'."
    },
    "support": {
        "question": "How do I contact customer support?",
        "answer": "You can reach us via email at support@example.com, call us at 1-800-555-0123 (Mon-Fri 9am-6pm EST), or use the live chat on our website."
    },
    "account": {
        "question": "How do I create an account?",
        "answer": "Click 'Sign Up' at the top right of our website. You can register with your email address or sign in using Google or Facebook accounts. Account creation is free and gives you access to order history and faster checkout."
    },
    "international": {
        "question": "Do you ship internationally?",
        "answer": "Yes, we ship to most countries worldwide. International shipping costs vary by destination and are calculated at checkout. Delivery times range from 7-21 business days depending on location."
    },
    "discounts": {
        "question": "Do you offer discounts or promotions?",
        "answer": "Yes! Sign up for our newsletter to receive 10% off your first order. We also run seasonal sales and offer student discounts (15% off with valid student ID)."
    },
    "price_match": {
        "question": "Do you offer price matching?",
        "answer": "Yes, we match prices from authorized retailers. Submit a price match request within 7 days of purchase with proof of the lower price, and we'll refund the difference."
    }
}


@function_tool
def lookup_faq(topic: str) -> str:
    """
    Look up answers to frequently asked questions.
    
    Args:
        topic: The topic or question keyword to search for (e.g., 'shipping', 'returns', 'warranty')
        
    Returns:
        A formatted string with the FAQ answer
    """
    topic_key = topic.lower().strip()
    
   
    if topic_key in FAQ_DB:
        faq = FAQ_DB[topic_key]
        return f"Q: {faq['question']}\nA: {faq['answer']}"
    
   
    matches = []
    for key, faq in FAQ_DB.items():
        if (topic_key in key or 
            topic_key in faq['question'].lower() or 
            topic_key in faq['answer'].lower()):
            matches.append((key, faq))
    
    if matches:
        results = []
        for key, faq in matches:
            results.append(f"Q: {faq['question']}\nA: {faq['answer']}")
        return "Found matching FAQs:\n\n" + "\n\n".join(results)
    
    return f"No FAQ found for '{topic}'. Available topics: {', '.join(FAQ_DB.keys())}"

