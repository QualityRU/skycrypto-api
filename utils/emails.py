import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import environ
from random import choice

from utils.email_texts.receipt import RECEIPT

# PAYMENT_EMAILS = [
#     {'email': email, 'password': password}
#     for email, password
#     in zip(
#         environ['PAYMENT_EMAILS'].split(','),
#         environ['PAYMENT_EMAIL_PASSWORDS'].split(','),
#     )
# ]


def receipt(recipient, paid, received, symbol, deal_id, closed_at, label, url, website, broker):
    email_object = choice(PAYMENT_EMAILS)
    sender_email = email_object['email']
    receiver_email = recipient
    password = email_object['password']

    message = MIMEMultipart("alternative")
    message["Subject"] = 'Электронный чек SKY'
    message["From"] = sender_email
    message["To"] = receiver_email

    html = RECEIPT.format(
        paid=paid, received=received, symbol=symbol,
        url=url, website=website, deal_id=deal_id,
        closed_at=closed_at, label=label, broker=broker
    )

    message.attach(MIMEText(html, "html"))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(
            sender_email, receiver_email, message.as_string().encode()
        )
