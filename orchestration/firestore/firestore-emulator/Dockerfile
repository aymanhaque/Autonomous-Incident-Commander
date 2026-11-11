# Firestore emulator image: Firebase publishes none, so we wrap firebase-tools.
# The emulator is a Java jar, so a JRE is required. node:20-slim + JRE stays small.
FROM node:20-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless wget \
 && rm -rf /var/lib/apt/lists/*
# Pin firebase-tools so the emulator version is reproducible across the team.
RUN npm i -g firebase-tools@13
WORKDIR /firebase
# firebase.json / rules / indexes are mounted by docker-compose at runtime.
# The start script imports prior data only if an export exists (safe first run).
COPY start-emulator.sh /usr/local/bin/start-emulator.sh
RUN sed -i 's/\r$//' /usr/local/bin/start-emulator.sh \
 && chmod +x /usr/local/bin/start-emulator.sh
EXPOSE 8080 4000
CMD ["/usr/local/bin/start-emulator.sh"]
