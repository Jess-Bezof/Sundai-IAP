from pydantic import BaseModel, Field

class SocialMediaPost(BaseModel):
    reasoning: str = Field(description="Explain how you applied the feedback/instructions to this post.")
    content: str = Field(min_length=10, max_length=500)
    hashtags: list[str]

class BusinessKeywords(BaseModel):
    primary_keywords: list[str] = Field(description="5 search terms for Mastodon")

class SingleReply(BaseModel):
    post_id: str
    reply_text: str = Field(description="A professional reply under 250 characters")

class ReplyBatch(BaseModel):
    all_replies: list[SingleReply]

class FeedbackSchema(BaseModel):
    original_content: str
    feedback_text: str
    embedding: list[float]
