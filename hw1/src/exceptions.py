class envNotFoundError(Exception):
    '''
    Exception raised when the .env file isn't found. Check directory for a .env file.
    '''
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
    
class keyNotFoundError(Exception):
    '''
    Exception raised when the key is not found. Ensure API keys in .env file
    is pasted correctly.
    '''
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
    
class invalidKeyError(Exception):
    '''
    Cleaner exception raised when a key is invalid: check
    .env file that the keys are pasted correctly?
    '''
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message