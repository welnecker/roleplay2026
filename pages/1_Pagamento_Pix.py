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
from persistence.v2_factory import build_v2_narrative_repositories


ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Pagamento Pix", page_icon="💠", layout="centered")
st.title("Pagamento por Pix")


@st.cache_resource(show_spinner=False)
def payment_services() -> tuple[
    PixCheckoutService | None,
    GoogleSheetsAccountRepository | None,
    object | None,
    str,
]:
    """Monta a infraestrutura Pix uma única vez por processo do Streamlit."""

    try:
        runtime = build_google_sheets_repository(st.secrets)
        if runtime is None:
            return None, None, None, "Google Sheets não está configurado."

        access_token = read_secret(
            st.secrets,
            "MERCADO_PAGO_ACCESS_TOKEN",
            "MERCADOPAGO_ACCESS_TOKEN",
            "MP_ACCESS_TOKEN",
        )
        if not access_token:
            return None, None, None, "Access Token do Mercado Pago não encontrado nos secrets."

        accounts = GoogleSheetsAccountRepository(runtime.spreadsheet)
        accounts.ensure_schema()
        payments = GoogleSheetsPaymentRepository(runtime.spreadsheet)
        payments.ensure_schema()
        v2_repositories = build_v2_narrative_repositories(st.secrets)
        service = PixCheckoutService(
            client=MercadoPagoClient(access_token),
            payments=payments,
            accounts=accounts,
            story_credits=v2_repositories.credits,
        )
        return service, accounts, v2_repositories.credits, ""
    except Exception as exc:
        return None, None, None, str(exc)


def is_sandbox_order(stored: StoredPaymentOrder) -> bool:
    """Reconhece uma cobrança de teste usando apenas campos persistidos."""

    evidence = " ".join(
        (
            str(getattr(stored, "qr_code", "") or ""),
            str(getattr(stored, "ticket_url", "") or ""),
            str(getattr(stored, "status_detail", "") or ""),
            str(getattr(stored, "external_reference", "") or ""),
        )
    ).upper()
    return "TESTUSER" in evidence or "@TESTUSER.COM" in evidence


def clear_pix_session(package_id: str) -> None:
    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)


if st.button("← Voltar à biblioteca"):
    st.session_state.page = "library"
    st.switch_page("app.py")

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

service, accounts, story_credits, service_error = payment_services()
if service is None or accounts is None or story_credits is None:
    st.error(service_error or "Não foi possível iniciar o pagamento.")
    st.stop()

manifest = package.manifest
commerce = manifest.commerce
if commerce.access != "paid" or commerce.price_cents <= 0:
    st.info("Esta história não exige pagamento.")
    st.stop()

if accounts.has_entitlement(
    user_id=str(user.user_id),
    package_id=manifest.package_id,
    access="paid",
):
    st.success("Esta história já está liberada para sua conta.")
    if st.button("Abrir história", type="primary", use_container_width=True):
        st.session_state.selected_package_id = manifest.package_id
        st.session_state.started_packages.add(manifest.package_id)
        st.session_state.page = "player"
        clear_pix_session(manifest.package_id)
        st.switch_page("app.py")
    st.stop()

st.subheader(manifest.card.title)
st.write(manifest.card.description)
st.metric(
    "Valor",
    f"R$ {commerce.price_cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
)

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

    status_label = stored.status or "pendente"
    st.info(f"Status atual: {status_label}")

    if is_sandbox_order(stored):
        st.caption("Cobrança de sandbox detectada. Nenhum valor real será movimentado.")
        if st.button(
            "Simular pagamento aprovado",
            type="primary",
            use_container_width=True,
        ):
            try:
                payment_id = stored.provider_order_id or stored.payment_order_id
                accounts.grant_entitlement(
                    user_id=str(user.user_id),
                    package_id=manifest.package_id,
                    product_id=manifest.package_id,
                    source="mercado_pago_sandbox",
                    payment_id=payment_id,
                )
                story_credits.create_credit(
                    user_id=str(user.user_id),
                    package_id=manifest.package_id,
                    payment_id=payment_id,
                )
            except (ValueError, RuntimeError) as exc:
                st.error(f"Não foi possível liberar a história: {exc}")
            else:
                clear_pix_session(manifest.package_id)
                st.session_state.selected_package_id = manifest.package_id
                st.session_state.started_packages.add(manifest.package_id)
                st.session_state.page = "player"
                st.success("Pagamento de teste aprovado. A história foi liberada.")
                st.switch_page("app.py")

    if st.button("Já paguei — verificar agora", use_container_width=True):
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
                clear_pix_session(manifest.package_id)
                st.session_state.selected_package_id = manifest.package_id
                st.session_state.started_packages.add(manifest.package_id)
                st.session_state.page = "player"
                st.success("Pagamento confirmado. A história foi liberada para sua conta.")
                st.switch_page("app.py")
            else:
                st.warning("O pagamento ainda não foi confirmado pelo Mercado Pago.")
                st.rerun()

    if st.button("Gerar uma nova cobrança", use_container_width=True):
        clear_pix_session(manifest.package_id)
        st.rerun()
