from gpt4all import GPT4All
from typing import Dict, List, Any

class UtilityBillLLM:
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        self.model_path = "./models/"
        self.model_name = model_name
        self.model = GPT4All(model_name, model_path=self.model_path)
        
    def get_response(self, query: str, bill_context: Dict[str, Any] = None) -> str:
        """
        Get a response from the LLM about a utility bill question
        
        Args:
            query: The user's question
            bill_context: Dictionary containing bill information
            
        Returns:
            The LLM's response
        """
        # Format the bill context as a string if provided
        context_str = ""
        if bill_context:
            context_str = "Bill Information:\n"
            for key, value in bill_context.items():
                context_str += f"- {key}: {value}\n"
        
        # Create a prompt with system instructions
        system_prompt = """You are Bill Buddy, an AI assistant specializing in explaining utility bills.
        Be concise, helpful, and focus on answering the user's question about their bill.
        If you don't know something, admit it rather than making up information."""
        
        # Combine all parts of the prompt
        full_prompt = f"""{system_prompt}
        
        {context_str}
        
        User Question: {query}
        
        Bill Buddy:"""
        
        # Generate response
        response = self.model.generate(full_prompt, max_tokens=512)
        return response

# Test the LLM
if __name__ == "__main__":
    # Sample bill data
    sample_bill = {
        "customer_name": "Jane Doe",
        "bill_date": "2025-04-01",
        "total_amount": "$127.35",
        "electricity_usage": "430 kWh",
        "green_energy_surcharge": "$20.00",
        "network_tariff": "$35.50"
    }
    
    llm = UtilityBillLLM()
    response = llm.get_response("What is the green energy surcharge?", sample_bill)
    print(response)