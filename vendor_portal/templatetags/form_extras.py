from django import template


register = template.Library()


@register.filter
def field_from_name(form, name):
    return form[name]


@register.simple_tag
def field_by_parts(form, *parts):
    return form["".join(str(part) for part in parts)]
