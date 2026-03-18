# Publish this project to GitHub

Your project is already committed locally and the remote is set to:

**https://github.com/michaelsam94/my-portfolio**

## 1. Create the repository on GitHub

1. Open **https://github.com/new**
2. Set **Repository name** to: `my-portfolio` (or another name you prefer)
3. Leave it **Public**
4. **Do not** check “Add a README”, “Add .gitignore”, or “Choose a license” (you already have these)
5. Click **Create repository**

## 2. Push your code

If you used the name **my-portfolio**:

```bash
cd /Users/tadafuqinformationtechnology/Desktop/my-portfolio
git push -u origin main
```

If you used a **different repository name**, update the remote and push:

```bash
git remote set-url origin https://github.com/michaelsam94/YOUR-REPO-NAME.git
git push -u origin main
```

You may be asked to sign in (browser or token). If you use 2FA, use a **Personal Access Token** instead of your password: GitHub → Settings → Developer settings → Personal access tokens.

After a successful push, your portfolio code will be at:

**https://github.com/michaelsam94/my-portfolio**
