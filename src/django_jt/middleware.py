class OverrideContentTypeMiddleware:
    """Set Content-Type to application/json when the client omitted it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.content_type:
            request.META["CONTENT_TYPE"] = "application/json"
        return self.get_response(request)
