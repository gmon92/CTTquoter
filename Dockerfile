FROM python:3.12-slim

WORKDIR /app

COPY app.py address_aliases.py base_rates.py quote_engine.py tomtom_client.py ./
COPY index.html "Taxi Pricing.xlsx" ./

ENV QUOTER_HOST=0.0.0.0
ENV PORT=8765

EXPOSE 8765

CMD ["python", "app.py"]
