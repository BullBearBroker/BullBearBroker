import { ChatPanel } from "@/components/chat/chat-panel";

export default function TestChatPage() {
  return (
    <div className="p-6 font-sans h-screen">
      <h1 className="mb-4 text-xl font-bold">🤖 Test Chat AI</h1>
      <div className="h-[85vh]">
        <ChatPanel token="demo-token" />
      </div>
    </div>
  );
}
