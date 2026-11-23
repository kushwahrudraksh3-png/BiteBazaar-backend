from io import BytesIO
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def generate_invoice_pdf(order):
    """Order object se PDF bytes generate karta hai."""
    items_list = []
    for sub_order in order.sub_orders.select_related('vendor').prefetch_related('items__food_item'):
        for item in sub_order.items.all():
            items_list.append({
                "restaurant_name": sub_order.vendor.restaurant_name,
                "name": item.food_item.name if item.food_item else "Deleted Item",
                "quantity": item.quantity,
                "price": item.price,
                "line_total": item.price * item.quantity,
            })

    html_string = render_to_string(
        "orders/invoice.html",
        {"order": order, "items_list": items_list},
    )

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=pdf_buffer)

    if pisa_status.err:
        return None

    return pdf_buffer.getvalue()


def send_order_receipt_email(order):
    """Customer ko PDF invoice attach karke email bhejta hai."""
    pdf_bytes = generate_invoice_pdf(order)
    if not pdf_bytes:
        return False

    subject = f"BiteBazaar Order #{order.id} Confirmed - Payment Receipt"
    body = (
        f"Hi {order.customer.first_name or 'Customer'},\n\n"
        f"Your payment of Rs. {order.total_price} for Order #{order.id} has been received successfully!\n"
        f"Please find your detailed order receipt attached as a PDF.\n\n"
        f"Thank you for ordering with BiteBazaar!"
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.customer.email],
    )
    email.attach(f"BiteBazaar_Invoice_Order_{order.id}.pdf", pdf_bytes, "application/pdf")
    email.send(fail_silently=False)
    return True