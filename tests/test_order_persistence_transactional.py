            self.assertEqual(2, version)
            self.assertIn("orders", tables)
            self.assertIn("ux_orders_one_pending_user", indexes)

    def test_telegram_final_selection_persists_pending_before_confirmation(self):
        from bot_ia.interfaces.telegram import TelegramAdapter

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            flow = BebidaOrderFlow()
            flow.start("user-1")
            flow.choose("user-1", "exposure", "SFW")
            flow.choose("user-1", "boldness", "Suave")
            flow.choose("user-1", "product_type", "Carta TCG")
            flow.choose("user-1", "resolution", "L")
            flow.choose("user-1", "render_style", "Classic Anime")

            adapter = TelegramAdapter.__new__(TelegramAdapter)
            adapter._bebida_flow = flow
            adapter._wallet_store = CafeWalletStore(root)
            adapter._order_store = OrderStore(root)
            adapter._pending_orders = {}
            adapter._last_orders = {}

            update = {
                "callback_query": {
                    "from": {"id": "user-1"},
                    "message": {"chat": {"id": "chat-1"}},
                    "data": "bebida:render_style:Classic Anime",
                }
            }
            outbound = adapter.handle_callback(update)
            pending = OrderStore(root).get_pending("user-1")
            self.assertIsNotNone(pending)

            payload = outbound.payload()
            buttons = payload["reply_markup"]["inline_keyboard"][0]
            callback_data = [button["callback_data"] for button in buttons]
            self.assertIn(
                f"order:confirm:{pending.order_id}",
                callback_data,
            )
            self.assertIn(
                f"order:cancel:{pending.order_id}",
                callback_data,
            )

            reopened = OrderStore(root)
            recovered = reopened.get_pending("user-1")
            self.assertEqual(pending, recovered)
            self.assertEqual(
                pending.order_id,
                recovered.order_id,
            )

    def test_pending_survives_restart_and_attachment_metadata_is_recoverable(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            order = _build_order()
            OrderStore(root).create_pending(order)

            reopened = OrderStore(root)
            recovered = reopened.get(order.order_id)