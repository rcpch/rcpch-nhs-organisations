from rest_framework import serializers
from ..models import PaediatricDiabetesNetwork


class PaediatricDiabetesNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaediatricDiabetesNetwork
        fields = ["pn_code", "name"]
