# Private access from phones with Cloudflare

People open a shared HTTPS address, sign in with an email code, and use the quoter in their phone's browser. Cloudflare Access limits entry to the email addresses you choose. Cloudflare Tunnel connects that address to the app running on your Mac.

The Mac must stay awake, online, and running the app and tunnel. The Mac's `.env` supplies the TomTom key, and its `Taxi Pricing.xlsx` supplies everyone's reference rates.

## What you need

- A Cloudflare account with an active domain. A domain registered elsewhere can use Cloudflare DNS; confirm the domain setup before changing business website or email DNS settings.
- A chosen address, such as `quoter.yourdomain.com`.
- The exact email addresses of the people who should have access, including yourself.
- The app working locally on the host Mac at `http://127.0.0.1:8765`.

The hostname below is an example. Substitute your own domain in the dashboard steps.

## 1. Set up email sign-in

In the Cloudflare dashboard, open **Zero Trust → Integrations → Identity providers**. Add **One-time PIN** if it is not already enabled.

People will use a code sent to their approved email address. They do not need to install a VPN app.

## 2. Protect the shared address

Create the Access application before adding a published tunnel route:

1. Open **Zero Trust → Access controls → Applications** and choose **Create new application**.
2. Choose the **Self-hosted and private** application type and add a **public hostname**.
3. Use a name such as **CTT Quoter** and the hostname `quoter.yourdomain.com`. Leave the path blank so the policy protects the entire app, including its quote and map endpoints.
4. Add an **Allow** policy named **Quoter users**. Use an **Include → Emails** rule containing only the individual approved email addresses. Do not add an Everyone rule, an email-domain-wide rule, or a Bypass policy.
5. Enable **One-time PIN** as a login method for this application. Choose a session duration appropriate for your group, for example one day.
6. Save the application. Keep its application audience (AUD) value available if requested when protecting the tunnel below.

## 3. Connect the Mac with a named tunnel

1. In the Cloudflare dashboard, go to **Networking → Tunnels** and create a Cloudflare Tunnel named **CTT Quoter**.
2. Choose **macOS**. Follow the dashboard's connector installation/run instructions on the Mac hosting the app. The dashboard provides the command for that specific tunnel. Keep its token on the host computer; it is not part of the app's GitHub files.
3. Wait for the connector to show as connected. A foreground connector must keep running; a connector installed as a service runs in the background.
4. On the tunnel's **Routes** tab, add a **Published application** route:

   | Field | Value |
   | --- | --- |
   | Subdomain | `quoter` |
   | Domain | Your Cloudflare domain |
   | Path | Leave blank |
   | Service type | HTTP |
   | Service URL | `127.0.0.1:8765` |

5. Enable **Protect with Access** for the route, using the Access application/team/audience settings Cloudflare requests. This lets the connector validate Access tokens before forwarding requests to the app.
6. Save the route. Cloudflare will configure the hostname's DNS record for the tunnel.

For this setup, use a named tunnel and the protected hostname, rather than a temporary public Quick Tunnel URL.

## 4. Start the app and check access

Double-click **Start Quoter.command** on the host Mac. Confirm that the app works locally, then open `https://quoter.yourdomain.com` in a private browser window.

Confirm that the shared address asks for sign-in first, an approved email can enter and calculate a quote, and an unapproved email cannot enter. Test the same address on a phone using cellular data to confirm that it works away from the host's Wi-Fi. Check both map loading and quote calculation after sign-in.

Once those checks pass, give the HTTPS address to the approved users. On iPhone they can use Safari's **Share → Add to Home Screen**; on Android they can use the browser's **Add to Home screen** option.

## Everyday use

- Keep the host Mac awake and connected to power while the quoter is available. Closing its lid normally puts it to sleep.
- Keep the app's Terminal window open and the Cloudflare connector running. Starting the existing quoter launcher starts the app; it does not install or start Cloudflare for you.
- Update `Taxi Pricing.xlsx` on the host Mac to change reference rates for future quotes.
- Add or remove individual emails in the Access policy to manage access. When removing someone who already signed in, also revoke their active Access sessions if access must end immediately.

If users see a Cloudflare gateway error, check that the app is running locally and that the connector is connected. If sign-in succeeds but calculating a quote reports TomTom HTTP 401, check the host Mac's `.env` key and restart the app.

## Cloudflare instructions

- [Create a tunnel in the dashboard](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)
- [Protect a self-hosted public application](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)
- [Configure email one-time PIN login](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/)
