class BusinessScopedQuerysetMixin:
    """
    Filters a view queryset to the active business attached by middleware.
    """

    business_field = "business"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(**{self.business_field: self.request.business})
