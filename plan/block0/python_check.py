from pydantic import BaseModel, Field


class Tally:
    def __init__(self):
        self.tally = 0
    
    def add(self, n):
        self.tally = self.tally + n
        
    def total(self):
        return self.tally
    
async def gather_two(first, second):
    await first()
    await second()
    
class Note(BaseModel):
    title: str = Field(min_length=1)
    words: int = Field(ge=0)
