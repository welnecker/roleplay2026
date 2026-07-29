from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from billing.mercado_pago import MercadoPagoClient, MercadoPagoError
from billing.service import PixCheckoutService, read_secret
from packages.loader import discover_packages
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.factory import build_google_sheets_repository
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Pagamento Pix", page_icon="💠", layout="centered")
st.title("Pagamento por Pix")

user = st.session_state.get("authenticated_user")
package_id = st.session_state.get("checkout_package_id")
if user is None:
    st.error("Entre na sua conta antes de iniciar o pagamento.")
    st.stop()
if not package_id:
    st.info("Escolha uma história paga na biblioteca antes de abrir esta página.")
    st.stop()

packages, errors = discover_packages(ROOT / "installed_stories")
package = next((item for item in packages if item.manifest.package_id == package_id), None)
if package is None:
    st.error("Pacote não encontrado.")
    if errors:
        st.code("\n".join(errors))
    st.stop()

runtime = build_google_sheets_repository(st.secrets)
if runtime is None:
    st.error("Google Sheets não está configurado.")
    st.stop()

access_token = read_secret(
    st.secrets,
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADOPAGO_ACCESS_TOKEN",
    "MP_ACCESS_TOKEN",
)
if not access_token:
    st.error("Access Token do Mercado Pago não encontrado nos secrets.")
    st.stop()

accounts = GoogleSheetsAccountRepository(runtime.spreadsheet)
accounts.ensure_schema()
payments = GoogleSheetsPaymentRepository(runtime.spreadsheet)
payments.ensure_schema()
service = PixCheckoutService(
    client=MercadoPagoClient(access_token),
    payments=payments,
    accounts=accounts,
)

manifest = package.manifest
commerce = manifest.commerce
if commerce.access != "paid" or commerce.price_cents <= 0:
    st.info("Esta história não exige pagamento.")
    st.stop()

st.subheader(manifest.card.title)
st.write(manifest.card.description)
st.metric("Valor", f"R$ {commerce.price_cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))

session_key = f"pix_order:{manifest.package_id}"
stored: StoredPaymentOrder | None = st.session_state.get(session_key)

if stored is None:
    if st.button("Gerar Pix", type="primary", use_container_width=True):
        try:
            with st.spinner("Criando cobrança Pix..."):
                result = service.create_checkout(
                    user_id=str(user.user_id),
                    payer_email=str(user.email),
                    package_id=manifest.package_id,
                    product_id=manifest.package_id,
                    title=manifest.card.title,
                    amount_cents=commerce.price_cents,
                    currency=commerce.currency,
                )
        except (MercadoPagoError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            stored = result.stored
            st.session_state[session_key] = stored
            st.session_state[f"pix_qr_base64:{manifest.package_id}"] = result.provider.qr_code_base64
            st.rerun()
else:
    qr_base64 = st.session_state.get(f"pix_qr_base64:{manifest.package_id}", "")
    if qr_base64:
        try:
            st.image(base64.b64decode(qr_base64), width=280)
        except (ValueError, TypeError):
            pass
    if stored.qr_code:
        st.text_area("Pix Copia e Cola", stored.qr_code, height=120)
    if stored.ticket_url:
        st.link_button("Abrir página do Pix", stored.ticket_url, use_container_width=True)

    status_label = stored.status or "pendente"
    st.info(f"Status atual: {status_label}")
    if st.button("Já paguei — verificar agora", type="primary", use_container_width=True):
        try:
            with st.spinner("Confirmando diretamente no Mercado Pago..."):
                result = service.refresh(stored)
        except (MercadoPagoError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            st.session_state[session_key] = result.stored
            if result.provider.qr_code_base64:
                st.session_state[f"pix_qr_base64:{manifest.package_id}"] = result.provider.qr_code_base64
            if result.provider.approved:
                st.success("Pagamento confirmado. A história foi liberada para sua conta.")
                st.session_state.page = "library"
            else:
                st.warning("O pagamento ainda não foi confirmado pelo Mercado Pago.")
            st.rerun()

    if st.button("Gerar uma nova cobrança", use_container_width=True):
        st.session_state.pop(session_key, None)
        st.session_state.pop(f"pix_qr_base64:{manifest.package_id}", None)
        st.rerun()
