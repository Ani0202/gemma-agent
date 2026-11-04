# Setup: about 45 minutes of your time, once

## A. Accounts (do today; only you can do these)
1. **Kaggle**
   - Open the competition, click *Join*, and accept the rules.
   - Go to *Settings → Phone verification*. This is required for GPUs.
   - Go to *Settings → API → Create New Token* to download `kaggle.json`.
2. **Google Cloud** (for the GPU VMs; the kit caps spend at $150)
   - Create a project such as `gemma-agent` and turn on billing. If the account is on the free
     trial, upgrade to a paid account: GPUs usually need it, and any trial credit still applies.
   - Enable the *Compute Engine API*.
   - Under *IAM & Admin → Quotas*, request:
     - `GPUS_ALL_REGIONS` = 4
     - L4 GPUs (including Spot/Preemptible) = 4 in one region, for example `us-central1`
     - Optionally, A100 80GB = 1

     Approval can take hours, so request these today.
   - Under *Billing → Budgets & alerts*, create a $150 budget with email alerts. This is a
     backstop; the kit enforces its own cap.
3. **Phone:** install the **ntfy** app (iOS or Android).
4. **Leave Etho alone.** Nothing in this kit touches it. It runs under a separate Claude login
   and a separate tmux session (`gemma`).

## B. On the Oracle VM
1. Copy the kit over: `scp gemma-kit.zip <vm>:~ && ssh <vm> 'unzip -q gemma-kit.zip && bash gemma-kit/setup_vm.sh'`.
   It asks for your sudo password once.
2. In the ntfy app, subscribe to **both** topics the script prints (server: ntfy.sh).
3. Do the secrets yourself:
   - `scp kaggle.json <vm>:~`, then on the VM run
     `mkdir -p ~/.kaggle && mv ~/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json`.
   - `gcloud auth login --no-launch-browser`, then `gcloud config set project <project-id>`.
   - Log in to Claude for this project only (your Etho login stays untouched). From `~/work/gemma`,
     run `CLAUDE_CONFIG_DIR=~/.claude-gemma claude`. Then:
     - `/login` with your university account, and accept the folder trust prompt.
     - `/config`: turn on **Push when Claude decides** and **Push when actions required**.
     - `/exit`.
   - On your phone, make sure the Claude app is signed in to the **same university account**, with
     notifications allowed. That's where the `gemma-builder` and `gemma-director` sessions appear.
   - If setup listed `codex` as MISSING, install it and run `codex login`.
4. Optional but handy: a private GitHub repo, so you can read reports from your phone. Data and
   traces are never committed.
   `cd ~/work/gemma && gh repo create gemma-agent --private --source . --push`
5. Start everything:
   ```
   cd ~/work/gemma && bin/install-autostart && bin/start
   ```
   This creates its own tmux session `gemma` with three windows: `builder`, `director`, `router`.
   Watch with `tmux attach -t gemma` and detach with **Ctrl-b, then d**. Stop with `bin/stop`.

## C. Remote Control
Both sessions turn on Remote Control at startup. On a university (Enterprise) plan, an Owner has to
enable Remote Control for the organization first. If the two sessions don't appear in the Claude
app's Code tab, ask UChicago IT to turn on "Remote Control" in the Claude Code admin settings.
Until then everything still works; you just talk to the system through ntfy instead of the app.

## D. Your job from now on
- **Talk to either session** in the Claude app (Code tab): `gemma-builder` or `gemma-director`.
  Plain messages from you are treated as owner instructions. The Builder forwards anything
  strategic to the Director.
- **Questions:** the Director pushes them to your phone (`E3: …`). Answer in the `gemma-director`
  session, or reply `E3: yes` in the ntfy `-reply` topic. Each question includes a recommendation
  and a default if you don't answer. Start an ntfy reply with `B:` to send it to the Builder instead.
- **Daily digest:** arrives around 8am Chicago time.
- **Controls:** reply `STOP`, `PAUSE`, `RESUME` or `STATUS` from the phone.
- **Look anytime:** `ssh <vm> 'cd ~/work/gemma && bin/status'`, or browse the GitHub repo.
- **Expected asks:** confirming the two finals (Dec 1), maybe a forum question to post from your
  account, and maybe a budget question.
