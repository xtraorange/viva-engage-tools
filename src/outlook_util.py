"""Outlook integration for sending emails via the Outlook client."""
from typing import Optional

try:
    import win32com.client
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False


def send_via_outlook(
    recipient: str,
    subject: str,
    body: str,
    csv_file: str = None,
    auto_send: bool = False,
) -> bool:
    """Send an email via the Outlook client.

    Args:
        recipient: recipient email address
        subject: email subject
        body: email body text
        csv_file: optional path to CSV file to attach
        auto_send: if True, automatically send email; if False, leave open for review

    Returns:
        True if successful, False otherwise.
    """
    if not OUTLOOK_AVAILABLE:
        print("Error: pywin32 is not installed. Cannot use Outlook integration.")
        return False

    try:
        # align with user-supplied working pattern
        from win32com import client as win32_client
        import win32gui, time, os

        outlook = win32_client.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = recipient
        mail.Subject = subject

        # Display the email to let Outlook insert the default signature
        mail.Display()
        time.sleep(1)
        signature = mail.HTMLBody if hasattr(mail, 'HTMLBody') else ''

        # convert body text to HTML
        body_html = body.replace('\n', '<br>')
        mail.HTMLBody = body_html + signature

        # attach csv file if provided
        if csv_file:
            try:
                absolute_path = os.path.abspath(csv_file)
                mail.Attachments.Add(absolute_path)
            except Exception as e:
                print(f"Warning: could not attach {csv_file}: {e}")

        if auto_send:
            mail.Send()
            return True
        else:
            # bring window to front
            def window_enum(hwnd, results):
                title = win32gui.GetWindowText(hwnd).lower()
                if 'untitled - message' in title:
                    win32gui.ShowWindow(hwnd, 5)
                    win32gui.SetForegroundWindow(hwnd)
            win32gui.EnumWindows(window_enum, None)
            return True
    except Exception as e:
        print(f"Error sending email via Outlook to {recipient}: {e}")
        return False
