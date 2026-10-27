"""Offline withdrawal regressions; fictional records and no external connections."""
import copy
from types import SimpleNamespace

import pytest
from test_salon import no_external_connections, run
from run_demo import business, make_db, new_id, le


@pytest.mark.parametrize("message", ["STOP", "stop", "StOp", "  STOP \n", "STOP!", "STOP.", "STOP!!!", "STOP?", "Please unsubscribe", "stop texting me", "no more emails"])
def test_explicit_withdrawal(message):
    assert le.OPT_OUT.search(message)


@pytest.mark.parametrize("message", ["Can I stop by tomorrow?", "Where is the bus stop?", "Don't stop", "stop by", "nonstop", "STOP123", "stop@example.com", "What does STOP mean?", "How do I stop receiving offers?", "STOP\nCan I book?", "", None])
def test_ordinary_inquiry_preserves_consent(message):
    async def check():
        db, biz = make_db(), business()
        lead = await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="alex@example.com", session_id="s")
        await le.handle_chat_consent(db, biz, "s", "hello", {"email": True, "sms": True})
        before = await db.leads.find_one({"lead_id": lead["lead_id"]})
        assert await le.handle_chat_consent(db, biz, "s", message, None) is None
        assert await db.leads.find_one({"lead_id": lead["lead_id"]}) == before
    run(check())


@pytest.mark.parametrize("initial", [None, True, False])
def test_withdrawal_overrides_existing_decisions_and_repeated_checkbox(initial):
    async def check():
        db, biz = make_db(), business()
        lead = await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="alex@example.com", session_id="s")
        for ch in le.CHANNELS:
            if initial is not None:
                await le.record_consent(db, biz["business_id"], lead["lead_id"], ch, initial, "prior decision", "test")
        inquiry = await le.record_consent(db, biz["business_id"], lead["lead_id"], le.INQUIRY, True, "personal reply", "test", channel_to_use="email")
        for message in ["STOP", "STOP!", "What does a haircut cost?"]:
            await le.handle_chat_consent(db, biz, "s", message, {"email": True, "sms": True})
        saved = await db.leads.find_one({"lead_id": lead["lead_id"]})
        assert all(saved["consent"][ch]["granted"] is False for ch in le.CHANNELS)
        assert saved["consent"][le.INQUIRY] == inquiry
        events = saved["consent_log"][(0 if initial is None else 2) + 1:]
        assert len(events) == 4  # Repeated requests remain audited, never grant.
        assert all(e["granted"] is False and e["source"] == "chat opt-out" for e in events)
        for ch in le.CHANNELS:
            await db.leads.update_one({"lead_id": lead["lead_id"]}, {"$push": {"drafts": {"draft_id": ch, "channel": ch, "kind": "marketing", "status": "pending", "message": "Offer"}}})
            with pytest.raises(le.LeadError) as exc:
                await le.approve_draft(db, new_id, biz["business_id"], lead["lead_id"], ch, "fictional-owner")
            assert exc.value.code == 403
        assert saved["follow_ups"] == []
    run(check())


def test_stop_before_capture_survives_stale_prompt_and_business_isolation():
    async def check():
        db, biz = make_db(), business()
        other = {**copy.deepcopy(biz), "business_id": "other_salon"}
        await le.upsert_lead(db, new_id, other, name="Alex Sample", email="alex@example.com", session_id="shared")
        await le.handle_chat_consent(db, other, "shared", "hello", {"email": True, "sms": True})
        before_leads = await db.leads.find({"business_id": other["business_id"]}).to_list(10)
        before_sessions = await db.chat_sessions.find({"business_id": other["business_id"]}).to_list(10)
        await le.mark_consent_asked(db, biz, "shared")
        assert await le.handle_chat_consent(db, biz, "shared", "STOP", {"email": True}) == "opted_out"
        await le.handle_chat_consent(db, biz, "shared", "both", {"email": True, "sms": True})
        lead = await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="alex@example.com", session_id="shared")
        saved = await db.leads.find_one({"lead_id": lead["lead_id"]})
        assert all(saved["consent"][ch]["granted"] is False for ch in le.CHANNELS)
        assert len(saved["consent_log"]) == 2
        assert await db.leads.find({"business_id": other["business_id"]}).to_list(10) == before_leads
        assert await db.chat_sessions.find({"business_id": other["business_id"]}).to_list(10) == before_sessions
    run(check())


@pytest.mark.parametrize('kind', ['marketing', le.INQUIRY])
@pytest.mark.parametrize('change', ['withdraw', 'approve', 'archive'])
def test_approval_rechecks_permission_and_pending_state(monkeypatch, kind, change):
    async def check():
        db, biz = make_db(), business()
        lead = await le.upsert_lead(db, new_id, biz, name='Alex Sample', email='alex@example.com', session_id='s')
        channel = le.INQUIRY if kind == le.INQUIRY else 'email'
        await le.record_consent(db, biz['business_id'], lead['lead_id'], channel, True, 'explicit permission', 'test', channel_to_use='email')
        await db.leads.update_one({'lead_id': lead['lead_id']}, {'$push': {'drafts': {
            'draft_id': 'race', 'channel': 'email', 'kind': kind, 'status': 'pending', 'message': 'Fictional reply'}}})
        collection = db.leads
        original_update = collection.update_one
        async def intervening_update(query, update, *args, **kwargs):
            if 'follow_ups' in update.get('$push', {}):
                field, value = {
                    'withdraw': (f'consent.{channel}.granted', False),
                    'approve': ('drafts.0.status', 'approved'),
                    'archive': ('archived', True),
                }[change]
                await original_update({'lead_id': lead['lead_id']}, {'$set': {field: value}})
            return await original_update(query, update, *args, **kwargs)
        monkeypatch.setattr(collection, 'update_one', intervening_update)
        with pytest.raises(le.LeadError) as exc:
            await le.approve_draft(SimpleNamespace(leads=collection), new_id, biz['business_id'], lead['lead_id'], 'race', 'fictional-owner')
        assert exc.value.code == 409
        saved = await db.leads.find_one({'lead_id': lead['lead_id']})
        assert saved['follow_ups'] == []
        if change != 'approve':
            assert saved['drafts'][0]['status'] == 'pending'
    run(check())


def test_approval_retry_logs_only_one_simulated_follow_up():
    async def check():
        db, biz = make_db(), business()
        lead = await le.upsert_lead(db, new_id, biz, name='Alex Sample', email='alex@example.com', session_id='s')
        await le.record_consent(db, biz['business_id'], lead['lead_id'], 'email', True, 'explicit permission', 'test')
        await db.leads.update_one({'lead_id': lead['lead_id']}, {'$push': {'drafts': {
            'draft_id': 'once', 'channel': 'email', 'kind': 'marketing', 'status': 'pending', 'message': 'Fictional offer'}}})
        first = await le.approve_draft(db, new_id, biz['business_id'], lead['lead_id'], 'once', 'fictional-owner')
        assert first['simulated'] is True and first['delivered'] is False
        with pytest.raises(le.LeadError):
            await le.approve_draft(db, new_id, biz['business_id'], lead['lead_id'], 'once', 'fictional-owner')
        saved = await db.leads.find_one({'lead_id': lead['lead_id']})
        assert len(saved['follow_ups']) == 1
    run(check())
