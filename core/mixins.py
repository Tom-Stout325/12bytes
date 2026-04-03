class BusinessScopedQuerysetMixin:
    business_field = "business"

    def get_queryset(self):
        queryset = super().get_queryset()
        business = getattr(self.request, "business", None)
        if business is None:
            return queryset.none()
        return queryset.filter(**{self.business_field: business})
