from __future__ import annotations

import base64
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import gspread
import streamlit as st
from gspread.exceptions import APIError

from billing.mercado_pago import MercadoPagoClient, MercadoPagoError
from billing.master_test import MasterTestPaymentService
from billing.service import PixCheckoutService, read_secret
from packages.loader import discover_packages
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder
from persistence.spreadsheet_config import read_spreadsheet_ids
from persistence.v2_google_sheets import GoogleSheetsStoryCreditRepository
from services.paid_run_access import prime_paid_access_available
from services.pwa import install_pwa_metadata

ROOT = Path(__file__).resolve().parent.parent
PROCESSING_COOLDOWN_SECONDS = 6.0
NEW_CHARGE_COOLDOWN_SECONDS = 65.0
T = TypeVar("T")

st.set_page_config(page_title="Pagamento Pix", page_icon="💠", layout="centered")
install_pwa_metadata()
st.title("Pagamento por Pix")


@st.cache_resource(show_spinner=False)
def payment_services() -> tuple[
    PixCheckoutService | None,
    GoogleSheetsStoryCreditRepository | None,
    MasterTestPaymentService | None,
    str,
]:
    """Monta somente a infraestrutura de ROLEPLAY_ACCOUNTS_BILLING."""

    try:
        credentials = st.secrets.get("gcp_service_account")
        if not credentials:
            return None, None, None, "Google Sheets não está configurado."

        access_token = read_secret(
            st.secrets,
            "MERCADO_PAGO_ACCESS_TOKEN",
            "MERCADOPAGO_ACCESS_TOKEN",
            "MP_ACCESS_TOKEN",
        )
        if not access_token:
            return None, None, None, "Access Token do Mercado Pago não encontrado nos secrets."

        spreadsheet_ids = read_spreadsheet_ids(st.secrets)
        client = gspread.service_account_from_dict(dict(credentials))
        accounts_billing = client.open_by_key(spreadsheet_ids.accounts_billing)

        payments = GoogleSheetsPaymentRepository(accounts_billing)
        payments.ensure_schema()
        story_credits = GoogleSheetsStoryCreditRepository(accounts_billing)
        accounts = GoogleSheetsAccountRepository(accounts_billing)
        service = PixCheckoutService(
            client=MercadoPagoClient(access_token),
            payments=payments,
            accounts=accounts,
            story_credits=story_credits,
        )
        master_test = MasterTestPaymentService(
            accounts=accounts,
            payments=payments,
            story_credits=story_credits,
            master_emails=str(st.secrets.get("PAYMENT_TEST_MASTER_EMAILS", "") or ""),
        )
        return service, story_credits, master_test, ""
    except Exception as exc:
        return None, None, None, str(exc)


def is_quota_error(exc: BaseException) -> bool:
    if not isinstance(exc, APIError):
        return False
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code == 429 or "429" in str(exc)


def call_with_quota_backoff(
    operation: Callable[[], T],
    *,
    status: object,
    action_label: str,
    max_attempts: int = 5,
) -> T:
    """Repete somente falhas 429 durante o processamento do pagamento."""

    for attempt in range(max_attempts):
        try:
            return operation()
        except APIError as exc:
            if not is_quota_error(exc) or attempt == max_attempts - 1:
                raise
            delay = min(30.0, (2 ** (attempt + 1)) + random.uniform(0.5, 1.5))
            write = getattr(status, "write", None)
            if callable(write):
                write(f"Aguardando para {action_label} ({delay:.0f} segundos)...")
            time.sleep(delay)

    raise RuntimeError(f"Não foi possível concluir: {action_label}.")


def clear_pix_session(package_id: str) -> None:
    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)


def prepare_new_charge(package_id: str) -> None:
    """Aguarda uma janela segura antes de reconstruir o checkout."""

    with st.status("Preparando uma nova cobrança...", expanded=True) as status:
        status.write("A cobrança anterior será descartada. Aguarde alguns instantes.")
        time.sleep(NEW_CHARGE_COOLDOWN_SECONDS)
        clear_pix_session(package_id)
        status.update(label="Nova cobrança pronta.", state="complete", expanded=False)
    st.rerun()


def finish_payment_transition(*, user_id: str, package_id: str, status: object) -> None:
    """Prepara o acesso local e abre a história sem nova leitura imediata."""

    prime_paid_access_available(
        secrets=st.secrets,
        user_id=user_id,
        package_id=package_id,
        ttl_seconds=90.0,
    )
    st.session_state["payment_access_ready"] = {
        "user_id": user_id,
        "package_id": package_id,
        "created_at": time.time(),
    }

    write = getattr(status, "write", None)
    if callable(write):
        write("Preparando a abertura da história...")
    time.sleep(PROCESSING_COOLDOWN_SECONDS)

    update = getattr(status, "update", None)
    if callable(update):
        update(label="Execução liberada!", state="complete", expanded=False)

    clear_pix_session(package_id)
    st.session_state.selected_package_id = package_id
    st.session_state.started_packages.add(package_id)
    st.session_state.page = "player"
    st.switch_page("app.py")


if st.button("← Voltar à biblioteca"):
    st.session_state.page = "library"
    st.session_state.checkout_package_id = None
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

service, story_credits, master_test, service_error = payment_services()
if service is None or story_credits is None or master_test is None:
    st.error(service_error or "Não foi possível iniciar o pagamento.")
    st.stop()

manifest = package.manifest
commerce = manifest.commerce
if commerce.access != "paid" or commerce.price_cents <= 0:
    st.info("Esta história não exige pagamento.")
    st.stop()

st.subheader(manifest.card.title)
st.write(manifest.card.description)
st.metric(
    "Valor",
    f"R$ {commerce.price_cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
)

is_master_test_user = master_test.is_authorized(user_id=str(user.user_id))
if is_master_test_user:
    st.caption("Ambiente interno de teste autorizado para esta conta.")
    if st.button("Liberar pagamento de teste", type="primary", use_container_width=True):
        try:
            with st.status("Registrando pagamento interno de teste...", expanded=True) as status:
                call_with_quota_backoff(
                    lambda: master_test.approve_test_payment(
                        user_id=str(user.user_id),
                        package_id=manifest.package_id,
                        amount_cents=commerce.price_cents,
                        currency=commerce.currency,
                    ),
                    status=status,
                    action_label="registrar o pagamento de teste",
                )
                status.write("Pagamento de teste auditado e crédito confirmado.")
                finish_payment_transition(
                    user_id=str(user.user_id),
                    package_id=manifest.package_id,
                    status=status,
                )
        except (APIError, PermissionError, ValueError, RuntimeError) as exc:
            st.error(f"Não foi possível concluir o pagamento de teste: {exc}")
    st.divider()

session_key = f"pix_order:{manifest.package_id}"
stored: StoredPaymentOrder | None = st.session_state.get(session_key)

if stored is None:
    if st.button("Gerar Pix", type="primary", use_container_width=True):
        try:
            with st.status("Criando cobrança Pix...", expanded=True) as creation_status:
                creation_status.write("Preparando os dados do pagamento...")
                result = call_with_quota_backoff(
                    lambda: service.create_checkout(
                        user_id=str(user.user_id),
                        payer_email=str(user.email),
                        package_id=manifest.package_id,
                        product_id=manifest.package_id,
                        title=manifest.card.title,
                        amount_cents=commerce.price_cents,
                        currency=commerce.currency,
                    ),
                    status=creation_status,
                    action_label="criar a cobrança Pix",
                )
                creation_status.update(
                    label="Cobrança Pix criada.",
                    state="complete",
                    expanded=False,
                )
        except (MercadoPagoError, APIError, PermissionError, ValueError, RuntimeError) as exc:
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

    if st.button("Já paguei — verificar agora", use_container_width=True):
        try:
            with st.status("Aguarde o processamento do pagamento...", expanded=True) as processing_status:
                processing_status.write("Confirmando diretamente no Mercado Pago...")
                result = call_with_quota_backoff(
                    lambda: service.refresh(stored),
                    status=processing_status,
                    action_label="confirmar o pagamento",
                )
                st.session_state[session_key] = result.stored
                if result.provider.qr_code_base64:
                    st.session_state[f"pix_qr_base64:{manifest.package_id}"] = (
                        result.provider.qr_code_base64
                    )

                if result.provider.approved:
                    processing_status.write("Pagamento aprovado e execução liberada.")
                    finish_payment_transition(
                        user_id=str(user.user_id),
                        package_id=manifest.package_id,
                        status=processing_status,
                    )
                else:
                    processing_status.update(
                        label="Pagamento ainda não confirmado.",
                        state="complete",
                        expanded=False,
                    )
                    st.warning("O pagamento ainda não foi confirmado pelo Mercado Pago.")
        except (MercadoPagoError, APIError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    if st.button("Gerar uma nova cobrança", use_container_width=True):
        prepare_new_charge(manifest.package_id)
