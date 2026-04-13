# Show your README on your GitHub **profile** (like [EslamFareed](https://github.com/EslamFareed))

GitHub only renders a profile “Overview” README from **one special repository**: the repo whose name **matches your username exactly**.

| Your username | Required repository name |
|---------------|---------------------------|
| `michaelsam94` | **`michaelsam94`** |

Official guide: [Managing your profile README](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/customizing-your-profile/managing-your-profile-readme).

---

## Step 1 — Create the repository on GitHub

1. Open **[github.com/new](https://github.com/new)** while logged in as **michaelsam94**.
2. **Repository name:** `michaelsam94` (same as username — required).
3. Set it **Public**.
4. **Do not** add a README, .gitignore, or license (you will push your own `README.md`).
5. Click **Create repository**.

---

## Step 2 — Add your profile `README.md`

This folder contains **`profile-README.md`** — that file is meant to become **`README.md`** in the `michaelsam94` repo (not in `my-portfolio`).

**Option A — GitHub web UI**

1. Open `https://github.com/michaelsam94/michaelsam94`.
2. **Add file** → **Create new file** → name it **`README.md`**.
3. Copy the **entire** contents of `profile-README.md` from this project and paste into GitHub.
4. Commit.

**Option B — From your computer**

```bash
# Copy the template and rename to README.md
cp profile-README.md README.md

mkdir -p ~/github-profile-michaelsam94
mv README.md ~/github-profile-michaelsam94/

cd ~/github-profile-michaelsam94
git init
git add README.md
git commit -m "Add profile README"
git branch -M main
git remote add origin https://github.com/michaelsam94/michaelsam94.git
git push -u origin main
```

If the repo was created empty, the push should succeed. If GitHub created a default branch with a commit, use:

`git pull origin main --rebase` then `git push -u origin main`.

---

## Step 3 — Confirm on your profile

Open **`https://github.com/michaelsam94`**.

Your README should appear **above** “Pinned” repositories, the same way it does for [EslamFareed](https://github.com/EslamFareed).

**Deep link to the first heading** (GitHub auto-generates the anchor from your `# Hi there...` title):

`https://github.com/michaelsam94#hi-there-im-michael-samuel-naeem-`

(If the anchor differs slightly, click the heading on your profile and copy the URL from the address bar.)

---

## What stays where

| Location | Purpose |
|----------|---------|
| Repo **`michaelsam94/michaelsam94`** + root **`README.md`** | Profile **Overview** (what you wanted) |
| Repo **`michaelsam94/my-portfolio`** + root **`README.md`** | README on the **portfolio repository** page only |

Keep both: profile repo for the landing story; `my-portfolio` for project + `npm run dev` instructions.
