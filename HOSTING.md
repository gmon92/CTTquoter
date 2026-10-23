# Host the quoter with an unlisted link

The quoter can run on Render while your business website stays at GoDaddy. GitHub supplies the code and pricing workbook; Render runs the Python server and provides an HTTPS web address. Your Mac can be turned off after deployment.

[Deploy this repository to Render](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fgmon92%2FCTTquoter)

## First deployment

1. Open the deployment link above and sign in to or create your Render account. Connect GitHub and grant Render access to `gmon92/CTTquoter` when prompted.
2. Render reads the repository's `render.yaml` blueprint. Review the **cttquoter** web service and **Free** instance plan.
3. When prompted for `TOMTOM_API_KEY`, paste your actual TomTom API key into Render's environment settings. Your local `.env` is excluded from Git and will not be deployed.
4. Create/deploy the service. Wait until Render reports it as **Live**, then open its assigned `https://…onrender.com` address.
5. Test a quote and map, including extra stops, charges, and tip. Share the HTTPS address with the people using the app.

The blueprint supplies the start command, public listening address, health endpoint, and automatic deployments from GitHub's `main` branch. No database, cloud file storage, or extra Python packages are required.

## Using it from phones

Everyone uses the Render address in their browser and can add it to their home screen. The server supplies routing and reference rates; each browser has its own quote controls.

The Free plan is intended for a trial. Render currently spins free web services down after 15 minutes without traffic; opening the app again can take about a minute while it wakes. A paid instance can avoid the idle wake-up delay if you later want that.

## Unlisted access

The app has no login in this setup. Its HTML and HTTP responses ask search engines not to index it. This discourages indexing; anyone who obtains or discovers the address can open it and generate TomTom API requests.

The TomTom key stays in Render's environment settings and is used by the server. The app's HTTP routes do not serve `.env` or the pricing workbook as downloads.

## Updates and pricing changes

Pushing changes to GitHub's `main` branch triggers a new Render deployment. Update `Taxi Pricing.xlsx` in GitHub and keep its table layout to deploy new base-rate references. A workbook edited only on your Mac does not update the hosted copy until it is committed and pushed.

To change the API key, edit `TOMTOM_API_KEY` in Render's environment settings and restart/redeploy the service. Do not add the key to GitHub.

## Optional: use your GoDaddy domain

After the Render address works, you can give the app a branded subdomain such as `quotes.yourdomain.com`:

1. Add that subdomain under the Render service's **Custom Domains** settings.
2. Render shows the DNS record needed for verification and routing. In GoDaddy's DNS management, add the record for the new subdomain using Render's exact instructions.
3. Wait for Render to verify the domain and issue its HTTPS certificate, then use the new address.

Use an unused subdomain. This setup does not require moving your main website or changing its existing root/`www` records or email records.

## Deployment checks

- `/health` returns HTTP 200 and `{"status":"ok"}` without making a TomTom request.
- The Python service listens on Render's `PORT`, with `QUOTER_HOST=0.0.0.0` and `QUOTER_OPEN_BROWSER=0`.
- Local Mac and Windows launchers still default to `127.0.0.1:8765` and open the browser normally.
- A TomTom HTTP 401 during quote calculation means the Render service's API key needs checking; it is separate from the key saved on your Mac.

References: [Render web services](https://render.com/docs/web-services), [blueprint configuration](https://render.com/docs/blueprint-spec), and [Free service behavior](https://render.com/docs/free).
