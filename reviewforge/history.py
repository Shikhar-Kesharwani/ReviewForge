from reviewforge.prompts import summarize, summary_prefix

class ChatSummary:
    def __init__(self, models=None, max_tokens=1024):
        self.models = models or []
        self.max_tokens = max_tokens

    def too_big(self, messages):
        if not self.models:
            return False
        total = sum(count for count, _ in self.tokenize(messages))
        return total > self.max_tokens

    def tokenize(self, messages):
        if not self.models:
            return [(0, msg) for msg in messages]
        model = self.models[0]
        return [(model.token_count([msg]), msg) for msg in messages]

    def summarize(self, messages, depth=0):
        if not self.too_big(messages):
            return messages
            
        summarized = self.summarize_real(messages, depth)
        
        # Ensure the last message is from assistant so it doesn't merge with the next user message
        if summarized and summarized[-1]["role"] != "assistant":
            summarized.append({"role": "assistant", "content": "Ok."})
            
        return summarized

    def summarize_real(self, messages, depth=0):
        if not messages:
            return []
            
        if not self.too_big(messages):
            return messages

        # Split messages in half
        split_idx = len(messages) // 2
        older_half = messages[:split_idx]
        newer_half = messages[split_idx:]

        # Summarize the older half
        summary_msg = self.summarize_all(older_half)
        
        combined = [summary_msg] + newer_half
        
        # If still too big, recurse
        if self.too_big(combined) and depth < 10:
            return self.summarize_real(combined, depth + 1)
            
        return combined

    def summarize_all(self, messages):
        if not self.models:
            content = "\n".join(m["content"] for m in messages if m["role"] != "system")
            return {"role": "user", "content": f"{summary_prefix}{content[:500]}..."}
            
        prompt = list(messages)
        prompt.append({"role": "system", "content": summarize})
        
        response_text = ""
        for model in self.models:
            try:
                from reviewforge.sendchat import simple_send_with_retries
                response_text = model.simple_send_with_retries(prompt)
                if response_text:
                    break
            except Exception:
                continue
                
        if not response_text:
            response_text = "Summarization failed."
            
        return {"role": "user", "content": f"{summary_prefix}{response_text}"}
