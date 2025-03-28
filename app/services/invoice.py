# invoice_email.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from jinja2 import Template
from datetime import datetime
import os
import uuid
import hashlib
import logging

# Import ReportLab components
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from app.config import SMTP_PASSWORD, SMTP_PORT, SMTP_USER, SMTP_SERVER

# Setup logging
logger = logging.getLogger(__name__)

# Configuration
SMTP_CONFIG = {
    "server": SMTP_SERVER,
    "port": SMTP_PORT,
    "email": SMTP_USER,
    "password": SMTP_PASSWORD
}

# Invoice storage configuration
INVOICE_STORAGE_PATH = "invoices/"
BASE_URL = "https://digitaloceanapis.comradehomes.me"

# Email template (same as before)
EMAIL_TEMPLATE = Template('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comrade Homes Invoice #{{ invoice_number }}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
        
        body { font-family: 'Poppins', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f9f9f9; }
        .email-container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .email-header { background: linear-gradient(135deg, #D31027 0%, #EA384D 100%); color: white; padding: 30px; text-align: center; }
        .logo { max-width: 150px; margin-bottom: 20px; }
        h1 { margin: 0; font-size: 24px; font-weight: 600; }
        .email-body { padding: 30px; }
        .invoice-details { background-color: #f5f5f5; border-radius: 6px; padding: 20px; margin-bottom: 25px; }
        .invoice-details h2 { margin-top: 0; font-size: 18px; color: #D31027; }
        .invoice-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
        .invoice-total { margin-top: 15px; font-weight: 700; font-size: 18px; text-align: right; color: #D31027; }
        .payment-options { background-color: #f5f5f5; border-radius: 6px; padding: 20px; margin-bottom: 25px; }
        .payment-option { display: flex; align-items: center; margin-bottom: 15px; }
        .payment-option img { width: 40px; margin-right: 15px; }
        .payment-button { display: inline-block; background-color: #D31027; color: white; padding: 12px 25px; border-radius: 4px; font-weight: 600; transition: background-color 0.3s; }
        .download-invoice { text-align: center; margin: 25px 0; }
        .email-footer { background-color: #333; color: white; text-align: center; padding: 20px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <img src="https://comradehomes.me/favicon.ico" alt="Comrade Homes Logo" class="logo">
            <h1>Your Invoice #{{ invoice_number }} is Ready</h1>
        </div>
        
        <div class="email-body">
            <p>Hello {{ customer_name }},</p>
            <p>Thank you for choosing <strong>Comrade Homes</strong>. Please find your invoice details below:</p>
            
            <div class="invoice-details">
                <h2>Invoice Summary</h2>
                <div class="invoice-item">
                    <span>Invoice Number:</span>
                    <span>#CH-{{ invoice_number }}</span>
                </div>
                <div class="invoice-item">
                    <span>Date Issued:</span>
                    <span>{{ issue_date }}</span>
                </div>
                <div class="invoice-item">
                    <span>Due Date:</span>
                    <span>{{ due_date }}</span>
                </div>
                <div class="invoice-item">
                    <span>Service:</span>
                    <span>{{ service_description }}</span>
                </div>
                <div class="invoice-total">
                    Total Due: {{ currency }} {{ amount/100 }}
                </div>
            </div>

            <div class="payment-options">
                <h2>Payment Methods</h2>
                <div class="payment-option">
                    <img src="https://comradehomes.me/stripe-logo.png" alt="Stripe">
                    <div>
                        <strong>Credit/Debit Card (Stripe)</strong>
                        <p>Secure online payment processing</p>
                        <a href="{{ stripe_url }}" class="payment-button">Pay with Stripe</a>
                    </div>
                </div>
                
                <div class="payment-option">
                    <img src="https://comradehomes.me/mpesa-logo.png" alt="M-Pesa">
                    <div>
                        <strong>M-Pesa Mobile Money</strong>
                        <p>Instant mobile payments</p>
                        <a href="{{ mpesa_url }}" class="payment-button">Pay with M-Pesa</a>
                    </div>
                </div>
                <div class="payment-option">
                    <img src="https://comradehomes.me/paypal-logo.png" alt="M-Pesa">
                    <div>
                        <strong>PayPal Payment</strong>
                        <p>Instant Credit card  payments</p>
                        <a href="{{ mpesa_url }}" class="payment-button">Pay credit card</a>
                    </div>
                </div>
            </div>

            <div class="download-invoice">
                {% if payment_status == 'PAID' %}
                    <p>Your payment has been received. Thank you!</p>
                    <a href="{{ download_url }}" class="payment-button">Download Invoice PDF</a>
                {% else %}
                    <a href="{{ download_url }}" class="payment-button">Download Invoice PDF</a>
                    <p style="margin-top: 15px; font-size: 0.9em;">A copy is also attached to this email</p>
                {% endif %}
            </div>

            <p>For questions, contact <a href="mailto:support@comradehomes.me">support@comradehomes.me</a></p>
            <p>Best regards,<br>The Comrade Homes Team</p>
        </div>

        <div class="email-footer">
            <p>© {{ year }} Comrade Homes. All rights reserved</p>
            <p><a href="https://comradehomes.me" style="color: white;">Visit our website</a></p>
            <p style="font-size: 0.8em; opacity: 0.8;">Invoice generated on {{ generated_at }}</p>
        </div>
    </div>
</body>
</html>
''')

def generate_secure_download_token(invoice_id, email):
    """Generate a secure token for invoice download"""
    secret_key = os.environ.get('DOWNLOAD_SECRET_KEY', 'secret-key')
    combined = f"{invoice_id}:{email}:{secret_key}"
    return hashlib.sha256(combined.encode()).hexdigest()

def create_invoice_pdf(invoice_data, file_path):
    """Generate a PDF invoice using ReportLab"""
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Set up the document
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='RightAlign',
        parent=styles['Normal'],
        alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name='CenterAlign',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        textColor=colors.HexColor('#D31027')
    ))
    styles.add(ParagraphStyle(
        name='InvoiceHeading',
        parent=styles['Heading2'],
        textColor=colors.HexColor('#D31027')
    ))
    
    # List to hold the flowables
    elements = []
    
    # Add company header
    # If you have a logo file, uncomment and update the path:
    try:
        logo = Image('https://www.comradehomes.me/favicon.ico',
                    width=2*inch,
                    height=1*inch)
        elements.append(logo)
    except:
        elements.append(Paragraph("Comrade Homes", styles['Title']))
    
    elements.append(Paragraph("COMRADE HOMES", styles['CenterAlign']))
    elements.append(Paragraph("INVOICE", styles['CenterAlign']))
    elements.append(Spacer(1, 0.25*inch))
    
    # Add invoice information
    invoice_info_data = [
        ["Invoice #:", f"CH-{invoice_data['invoice_number']}"],
        ["Date Issued:", invoice_data['issue_date']],
        ["Due Date:", invoice_data['due_date']],
        ["Status:", invoice_data.get('payment_status', 'CONFIRMED')]
    ]
    
    invoice_info_table = Table(invoice_info_data, colWidths=[1.5*inch, 4*inch])
    invoice_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(invoice_info_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Customer information
    elements.append(Paragraph("Bill To:", styles['InvoiceHeading']))
    elements.append(Paragraph(f"Name: {invoice_data['customer_name']}", styles['Normal']))
    elements.append(Paragraph(f"Email: {invoice_data['customer_email']}", styles['Normal']))
    elements.append(Paragraph(f"Billed Through: {invoice_data['payment_by']}", styles['Normal']))
    
    elements.append(Spacer(1, 0.25*inch))
    
    # Invoice items
    elements.append(Paragraph("Invoice Details", styles['InvoiceHeading']))
    
    # For simplicity, we're assuming a single line item from service description
    item_data = [
        ['Description', 'Amount'],
        [invoice_data['service_description'], f"{invoice_data['currency']} {invoice_data['amount']/100}"]
    ]
    
    # Add total row
    item_data.append(['Total', f"{invoice_data['currency']} {invoice_data['amount']/100}"])
    
    # Create the table
    items_table = Table(item_data, colWidths=[4*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D31027')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # If it's a paid invoice, add payment information
    if invoice_data.get('payment_status') == 'PAID':
        elements.append(Paragraph("Payment Information", styles['InvoiceHeading']))
        elements.append(Paragraph(f"Payment Date: {invoice_data.get('payment_date', datetime.now().strftime('%Y-%m-%d'))}", styles['Normal']))
        elements.append(Paragraph(f"Payment Type: {invoice_data['payment_by']}", styles['Normal']))
        elements.append(Paragraph("Thank you for your payment!", styles['Normal']))
        elements.append(Spacer(1, 0.25*inch))
    
    # Footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("Thank you for choosing Comrade Homes", styles['CenterAlign']))
    elements.append(Paragraph(f"Generated on {invoice_data['generated_at']}", styles['RightAlign']))
    
    # Build the PDF
    doc.build(elements)
    
    return file_path

def save_invoice_for_download(invoice_data):
    """Save the invoice PDF using ReportLab for later download"""
    # Create directory if it doesn't exist
    os.makedirs(INVOICE_STORAGE_PATH, exist_ok=True)
    
    # Generate unique filename
    filename = f"invoice_{invoice_data['invoice_number']}_{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(INVOICE_STORAGE_PATH, filename)
    
    # Generate PDF using ReportLab
    create_invoice_pdf(invoice_data, file_path)
    
    # Generate download token
    token = generate_secure_download_token(invoice_data['invoice_number'], invoice_data['customer_email'])
    
    # Create download URL
    download_url = f"{BASE_URL}/download-invoice/{filename}?token={token}&email={invoice_data['customer_email']}"
    
    return download_url, file_path

def send_invoice(invoice_data, payment_completed=True):
    """Generate and send invoice email with ReportLab PDF generation"""
    # Generate timestamps
    invoice_data['year'] = datetime.now().year
    invoice_data['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Set payment status if provided
    if payment_completed:
        invoice_data['payment_status'] = 'PAID'
    else:
        invoice_data['payment_status'] = 'PENDING'
    
    # Save invoice and get download URL
    download_url, file_path = save_invoice_for_download(invoice_data)
    
    # Add download URL to invoice data
    invoice_data['download_url'] = download_url
    
    # Render HTML email with the download link
    html_content = EMAIL_TEMPLATE.render(**invoice_data)
    
    # Create email message
    msg = MIMEMultipart()
    msg['Subject'] = f"Comrade Homes Invoice #{invoice_data['invoice_number']}"
    msg['From'] = SMTP_CONFIG['email']
    msg['To'] = invoice_data['customer_email']
    
    # Attach HTML
    msg.attach(MIMEText(html_content, 'html'))
    
    # Attach PDF
    with open(file_path, 'rb') as f:
        part = MIMEApplication(f.read(), Name=f"Invoice_{invoice_data['invoice_number']}.pdf")
    part['Content-Disposition'] = f'attachment; filename="Invoice_{invoice_data["invoice_number"]}.pdf"'
    msg.attach(part)
    
    # Send email
    try:
        with smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port']) as server:
            server.starttls()
            server.login(SMTP_CONFIG['email'], SMTP_CONFIG['password'])
            server.sendmail(SMTP_CONFIG['email'], invoice_data['customer_email'], msg.as_string())
        logger.info(f"Invoice email sent successfully to {invoice_data['customer_email']}")
        return download_url
    except Exception as e:
        logger.error(f"Error sending invoice email: {str(e)}")
        raise

def handle_successful_payment(payment_data):
    """Call this function when payment is successful"""
    invoice_data = {
        'invoice_number': payment_data['invoice_id'],
        'customer_name': payment_data['customer_name'],
        'customer_email': payment_data['customer_email'],
        'issue_date': payment_data.get('issue_date', datetime.now().strftime("%Y-%m-%d")),
        'due_date': payment_data.get('due_date', datetime.now().strftime("%Y-%m-%d")),
        'service_description': payment_data['service_description'],
        'currency': payment_data['currency'],
        'amount': payment_data['amount'],
        'payment_by': payment_data['payment_by'],
        'payment_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Generate and send the paid invoice
    download_url = send_invoice(invoice_data, payment_completed=True)
    
    # Return the download URL for use in the payment confirmation page
    return download_url