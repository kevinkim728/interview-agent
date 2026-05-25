const MODEL = "gpt-realtime-mini";

class RealtimeClient {
    constructor() {
        this.pc = null;
        this.audioEl = null;
        this.dc = null;
        this.mediaRecorder = null;
        this.recordedChunks = [];
    }

    async connect() {
        try {
            console.log("1. Starting connection...");

            // Get ephemeral key from your server
            const tokenResponse = await fetch("/session");
            console.log("2. Token response status:", tokenResponse.status);

            const data = await tokenResponse.json();
            console.log("3. Full session data:", data);

            const EPHEMERAL_KEY = data.client_secret;
            console.log("4. Ephemeral key:", EPHEMERAL_KEY);

            // Create peer connection
            this.pc = new RTCPeerConnection();
            console.log("5. Created peer connection");

            // Set up audio playback for AI responses
            this.audioEl = document.createElement("audio");
            this.audioEl.autoplay = true;
            document.body.appendChild(this.audioEl);
            console.log("6. Created audio element");

            this.pc.ontrack = e => {
                console.log("7. Received audio track from AI");
                this.audioEl.srcObject = e.streams[0];

                // Add AI audio to the mixed recording
                if (this.audioContext && !this.aiSource) {
                    this.aiSource = this.audioContext.createMediaStreamSource(e.streams[0]);
                    this.aiSource.connect(this.mixedDestination);
                    console.log("🎙️ AI audio added to recording");
                }
            };

            // Add microphone input
            console.log("8. Requesting microphone access...");
            const ms = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log("9. Got microphone access - success!");
            this.startRecording(ms);
            this.pc.addTrack(ms.getTracks()[0]);

            // Set up data channel for events
            console.log("10. Creating data channel...");
            this.dc = this.pc.createDataChannel("oai-events");

            this.dc.addEventListener("open", () => {
                console.log("11. Data channel opened - ready for conversation!");

                // Add delay to ensure connection is fully ready
                setTimeout(() => {

                    const startMessage = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Hello, I'm ready to start the interview."}]
                        }
                    };

                    this.dc.send(JSON.stringify(startMessage));

                    // Tell AI to respond
                    const responseMessage = {
                        "type": "response.create"
                    };

                    this.dc.send(JSON.stringify(responseMessage));

                }, 1000);
            });

            this.dc.addEventListener("message", (e) => {
                console.log("12. Received message from AI:", JSON.parse(e.data));
            });

            // Start the session using the Session Description Protocol (SDP)
            console.log("13. Creating WebRTC offer...");
            const offer = await this.pc.createOffer();
            await this.pc.setLocalDescription(offer);
            console.log("14. Set local description");

            console.log("15. Sending offer to OpenAI...");
            const sdpResponse = await fetch("https://api.openai.com/v1/realtime/calls", {
                method: "POST",
                body: offer.sdp,
                headers: {
                    Authorization: `Bearer ${EPHEMERAL_KEY}`,
                    "Content-Type": "application/sdp",
                },
            });

            console.log("16. OpenAI response status:", sdpResponse.status);

            if (!sdpResponse.ok) {
                const errorText = await sdpResponse.text();
                console.error("17. OpenAI error:", errorText);
                return;
            }

            const answer = {
                type: "answer",
                sdp: await sdpResponse.text(),
            };

            await this.pc.setRemoteDescription(answer);
            console.log("18. ✅ Connected to OpenAI Realtime API via WebRTC!");
            console.log("19. 🎤 You can now speak - the AI will respond!");

        } catch (error) {
            console.error("❌ Connection failed:", error);
        }
    }

    startRecording(userStream) {
        // Create audio context for mixing
        this.audioContext = new AudioContext();

        // Create sources for both streams
        this.userSource = this.audioContext.createMediaStreamSource(userStream);
        this.aiSource = null; // Will be set when AI audio arrives

        // Create destination for mixed audio
        this.mixedDestination = this.audioContext.createMediaStreamDestination();

        // Connect user audio to mixed stream
        this.userSource.connect(this.mixedDestination);

        // Start recording the mixed stream
        this.mediaRecorder = new MediaRecorder(this.mixedDestination.stream);
        this.recordedChunks = [];

        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.recordedChunks.push(event.data);
            }
        };

        this.mediaRecorder.start();
        console.log("🎙️ Recording both sides started");
    }
}
