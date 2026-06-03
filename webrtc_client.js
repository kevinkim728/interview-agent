const MODEL = "gpt-realtime-2";

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
            const tokenResponse = await fetch("/session"); // Uses fetch to make a get request to /session. It responds with a Response object
            console.log("2. Token response status:", tokenResponse.status);

            const data = await tokenResponse.json(); //Parses the JSONResponse object from /session back to a JavaScript object (aka dict in python)
            console.log("3. Full session data:", data);

            const EPHEMERAL_KEY = data.client_secret; // Gets the client_secret which is the Ephemeral Key to use in the webrtc
            console.log("4. Ephemeral key:", EPHEMERAL_KEY);

            // Create peer connection
            this.pc = new RTCPeerConnection(); // Create an instance of the RTCPeerConnection class.
            console.log("5. Created peer connection");

            // Set up audio playback for AI responses
            this.audioEl = document.createElement("audio"); // Creates an "audio" html tag that will be used later
            this.audioEl.autoplay = true;
            document.body.appendChild(this.audioEl); // Appends the audio element to the end of the body of the HTML page
            console.log("6. Created audio element");

            // Ontrack listens to this.pc for any audio so that it can send it to me
            // Ontrack is how audio comes to me, addTrack is when audio goes out from me
            this.pc.ontrack = e => {
                console.log("7. Received audio track from AI");
                this.audioEl.srcObject = e.streams[0]; // Play the AI's audio into the audio element we made

                // Add AI audio to the mixed recording
                if (this.audioContext && !this.aiSource) { // If this.audioContext exists and this.aiSource hasn't been added to the recording yet
                    this.aiSource = this.audioContext.createMediaStreamSource(e.streams[0]); // Capture the AI's audio stream
                    this.aiSource.connect(this.mixedDestination); // Add the AI's audio to the mixed recording
                    console.log("🎙️ AI audio added to recording");
                }
            };

            // Add microphone input
            console.log("8. Requesting microphone access...");
            const ms = await navigator.mediaDevices.getUserMedia({ audio: true }); // Requests microphone access from the user in browser. navigator.mediaDevices is a built-in browser API
            console.log("9. Got microphone access - success!");
            this.startRecording(ms); // Starts recording the microphone audio stream
            this.pc.addTrack(ms.getTracks()[0]); // Adds your microphone audio to the peer connection so OpenAI can hear you

            // Creates a data channel on the peer connection for sending and receiving text events — not audio, just JSON messages back and forth between you and OpenAI.
            // OpenAI uses it to trigger when to create a response etc.
            console.log("10. Creating data channel...");
            this.dc = this.pc.createDataChannel("oai-events"); //createDataChannel is a method for RTCPeerConnection(). oai-events is what openAI expects the name of the channel to be

            this.dc.addEventListener("open", () => { // opens the channel
                console.log("11. Data channel opened - ready for conversation!");

                // Add delay to ensure connection is fully ready
                setTimeout(() => {

                    // This adds a message to the conversation as if the user typed it — it's what triggers the AI to start the interview.
                    const startMessage = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Hello, I'm ready to start the interview."}]
                        }
                    };

                    this.dc.send(JSON.stringify(startMessage)); // Sends open AI the control message to start the interview

                    // Tell AI to respond to the startMessage
                    const responseMessage = {
                        "type": "response.create"
                    };

                    this.dc.send(JSON.stringify(responseMessage)); // Sends open AI the control message with response.create

                }, 1000);
            });

            // See when control messages are being created and sent
            this.dc.addEventListener("message", (e) => {
                console.log("12. Received message from AI:", JSON.parse(e.data));
            });

            // Start the session using the Session Description Protocol (SDP). SDP describes what audio formats your browser supports
            console.log("13. Creating WebRTC offer...");
            const offer = await this.pc.createOffer(); //createOffer() is a built-in method on RTCPeerConnection that generates the SDP offer
            await this.pc.setLocalDescription(offer);// Stores the offer which is basically the settings for the call to ensure compatibility
            console.log("14. Set local description");

            console.log("15. Sending offer to OpenAI...");
            // The browser now sends the SDP offer as the body and the ephemeral_key as the header.
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

            // OpenAI's response with their SDP
            const answer = {
                type: "answer",
                sdp: await sdpResponse.text(),
            };

            await this.pc.setRemoteDescription(answer); // Sets OpenAI's answer as the remote description. If theres no overlap with the local description then it will fail
            console.log("18. ✅ Connected to OpenAI Realtime API via WebRTC!");
            console.log("19. 🎤 You can now speak - the AI will respond!");

        } catch (error) {
            console.error("❌ Connection failed:", error);
        }
    }

    startRecording(userStream) {
        // Create audio context for mixing
        this.audioContext = new AudioContext(); // Built-in browser API for processing audio

        // Create sources for both streams
        this.userSource = this.audioContext.createMediaStreamSource(userStream); // Creates an audio source from your microphone stream
        this.aiSource = null; // Will be set later when AI audio arrives through ontrack

        // Creates the destination for a consolidated stream
        this.mixedDestination = this.audioContext.createMediaStreamDestination(); 

        // Connect user audio to mixed stream
        this.userSource.connect(this.mixedDestination);

        // Start recording the mixed stream
        this.mediaRecorder = new MediaRecorder(this.mixedDestination.stream);
        this.recordedChunks = [];

        this.mediaRecorder.ondataavailable = (event) => { // ondataavailable is a built-in event on MediaRecorder that fires periodically with chunks of recorded audio
            if (event.data.size > 0) { //I f it has data (size > 0),
                this.recordedChunks.push(event.data); // It gets pushed into the recordedChunks array
            }
        };

        this.mediaRecorder.start();
        console.log("🎙️ Recording both sides started");
    }

    async stopRecordingAndSave() {
        return new Promise((resolve) => { // Promise object is created which is waiting for resolve() to be called
            this.mediaRecorder.onstop = async () => { // Event handler that waits for .stop() to be called before running
                const audioBlob = new Blob(this.recordedChunks, { type: 'audio/wav' });
                await this.saveInterview(audioBlob);
                resolve();
            };
            this.mediaRecorder.stop();
        });
    }

    async saveInterview(audioBlob) {
        const formData = new FormData(); // FormData is a built-in browser class for sending files over HTTP — like an audio file
        formData.append('audio', audioBlob, 'interview.wav');

        const response = await fetch('/save-interview', { 
            method: 'POST',
            body: formData
        });

        console.log("Interview saved:", await response.json());
    }

    async disconnect() {
        console.log("🔌 Disconnecting...");

        // Wait for recording to save before closing connections
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            console.log("💾 Saving recording...");
            await this.stopRecordingAndSave();  // Wait for this to complete
            console.log("✅ Recording saved");
        }

        // Now safely close connections
        if (this.dc) {
            this.dc.close();
            this.dc = null;
        }
        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }
        if (this.audioEl) {
            this.audioEl.srcObject = null;
            this.audioEl.remove();
            this.audioEl = null;
        }

        console.log("✅ Disconnected cleanly.");
    }
}