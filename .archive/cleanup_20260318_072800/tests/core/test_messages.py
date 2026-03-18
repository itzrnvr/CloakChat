import pytest
from core.data.messages import Message, Conversation

class TestMessage:
    def test_create_message(self):
        m = Message(role="user", content="Hello")
        assert m.role == "user"
        assert m.content == "Hello"
        assert m.timestamp is not None
    
    def test_message_equality(self):
        timestamp = None
        m1 = Message(role="user", content="Hello", timestamp=timestamp)
        m2 = Message(role="user", content="Hello", timestamp=timestamp)
        assert m1.role == m2.role
        assert m1.content == m2.content

class TestConversation:
    def test_empty_conversation(self):
        c = Conversation()
        assert c.messages == ()
        assert c.conversation_id is None
    
    def test_add_message(self):
        c = Conversation()
        c2 = c.add_message("user", "Hello")
        
        assert len(c.messages) == 0
        assert len(c2.messages) == 1
        assert c2.messages[0].content == "Hello"
    
    def test_immutability(self):
        c = Conversation()
        c.add_message("user", "Hello")
        
        assert len(c.messages) == 0
    
    def test_get_last_message(self):
        c = Conversation().add_message("user", "Hello").add_message("assistant", "Hi")
        assert c.get_last_message().content == "Hi"
    
    def test_get_user_messages(self):
        c = (
            Conversation()
            .add_message("system", "You are helpful")
            .add_message("user", "Hello")
            .add_message("assistant", "Hi")
            .add_message("user", "Bye")
        )
        
        user_messages = c.get_user_messages()
        assert len(user_messages) == 2
    
    def test_with_system_prompt(self):
        c = Conversation()
        c2 = c.with_system_prompt("You are a helpful assistant.")
        
        assert len(c.messages) == 0
        assert len(c2.messages) == 1
        assert c2.messages[0].role == "system"
