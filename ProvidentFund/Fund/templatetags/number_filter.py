from django import template

register = template.Library()

# Additional Library to convert longer numbers into shorter form eg. 1000000 >> 1M

@register.filter
def abbreviate_number(value):
    try:
        value = int(value)
        if value>= 1_000_000:
            return f'{value/1_000_000:.1f}M'
        elif value>=1_000:
            return f'{value/1_000:.1f}K'
        else:
            return str(value)
    except(ValueError,TypeError):
        return value