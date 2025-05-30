from rest_framework import serializers
from .models import Setting
import json # For validating and parsing JSON type settings

class SettingSerializer(serializers.ModelSerializer):
    # value_display = serializers.SerializerMethodField() # To show typed value on read

    class Meta:
        model = Setting
        fields = ['id', 'key', 'value', 'value_type', 'group', 'description', 'is_public', 'is_editable', 'created_at', 'updated_at']
        read_only_fields = ('created_at', 'updated_at')
        # `is_editable` is more of a flag for UI/business logic; actual field editability based on this
        # would typically be enforced in the view or serializer's update method if strictly needed.
        # For instance, an admin might still be able to edit a non-editable field if they have direct model access.

    # def get_value_display(self, obj):
    #     return obj.get_value() # Use the model's method to get typed value

    def validate_value(self, value):
        # Access value_type from initial_data or instance if available
        # This is a bit tricky as value_type might not be in `value`'s context directly during field validation
        # It's better to do this kind of validation in the `validate` method below.
        return value

    def validate(self, data):
        # Get value_type: if updating, use the instance's current value_type if not provided in data,
        # or use the one from data if it is being changed. If creating, use data's value_type.
        value_type = data.get('value_type', getattr(self.instance, 'value_type', None))
        value = data.get('value', getattr(self.instance, 'value', None))

        if not value_type: # Should not happen if field is required, but good for safety
            raise serializers.ValidationError({"value_type": "This field is required."})
        if value is None: # Should not happen
            raise serializers.ValidationError({"value": "This field is required."})


        if value_type == 'json':
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError({'value': 'Invalid JSON format.'})
        elif value_type == 'number':
            try:
                float(value) # Allows int or float strings
            except ValueError:
                raise serializers.ValidationError({'value': 'Invalid number format.'})
        elif value_type == 'boolean':
            if str(value).lower() not in ['true', 'false', '1', '0']:
                raise serializers.ValidationError({'value': "Invalid boolean. Use 'true', 'false', '1', or '0'."})
        
        # Check for is_editable constraint if trying to update value or value_type of a non-editable setting
        if self.instance and not self.instance.is_editable:
            # If it's an update and the setting is not editable by users/API
            changed_restricted_fields = False
            if 'value' in data and data['value'] != self.instance.value:
                changed_restricted_fields = True
            if 'value_type' in data and data['value_type'] != self.instance.value_type:
                changed_restricted_fields = True
            
            if changed_restricted_fields:
                 raise serializers.ValidationError(f"Setting '{self.instance.key}' is not editable for its value or type.")
        
        return data
    
    def to_representation(self, instance):
        """Convert `value` string to its Python type for API responses."""
        representation = super().to_representation(instance)
        representation['value'] = instance.get_value()
        return representation
