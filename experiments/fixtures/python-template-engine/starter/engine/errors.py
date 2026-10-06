class TemplateError(Exception):
    pass


class TemplateSyntaxError(TemplateError):
    def __init__(self, message, line, column):
        super().__init__(f'{line}:{column}: {message}')
        self.message = message
        self.line = line
        self.column = column
