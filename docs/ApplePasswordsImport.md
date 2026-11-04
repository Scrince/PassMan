# Importing Apple Passwords into PassMan

This guide walks through exporting passwords from the **Passwords** app on macOS
and importing them into an open PassMan vault.

## Before you start

Open PassMan and unlock the vault that should receive the entries. Make sure
there is enough free space for the vault save. Apple exports a plain CSV file:
the passwords in that file are not encrypted while it exists, so save it in a
private location and remove it after the import.

## Export a CSV from Passwords on Mac

1. Open the **Passwords** app on your Mac.
2. In the menu bar, choose **File → Export All Passwords to File…**.
3. Confirm **Export Passwords** when prompted.
4. In the save dialog, choose a private location you can find again, such as a
   folder in your home directory. Save the exported `.csv` file.
5. If macOS asks for permission to export or authenticate, follow the on-screen
   prompt.

You can export a single selected account instead by selecting it in Passwords
and choosing **File → Export Selected Password to File…**. That is useful for
trying the workflow with one entry first.

## Import the CSV in PassMan

1. In PassMan, check that the intended vault is open and unlocked.
2. Click **Import** in the left sidebar. The button is below
   **Password Generator** and above **Backup**.
3. In the file picker, select the CSV exported from Passwords and click
   **Open**.
4. PassMan reads the file locally and shows a confirmation with the number of
   entries it expects to **add**, **update**, leave **unchanged**, and delete.
   Deletion applies only to entries previously created by this Apple Passwords
   import. If the CSV has an `OTPAuth` column, the dialog also lists
   authenticator codes to add, update, leave unchanged, or delete. Choose **Yes**
   to apply the import, or **No** to cancel without changing the vault.
5. When the import finishes, PassMan reports the actual added, updated,
   unchanged, and deleted counts for password entries and, when present,
   authenticator codes. The changes are saved in the encrypted vault.

For example, import a CSV containing Alice at `https://example.com` and Bob at
`https://example.net`. PassMan creates two Apple-managed entries. If Alice's
password changes in Apple Passwords, import the new CSV: her existing PassMan
entry is updated (keeping its PassMan entry identity and custom fields), and
Bob's entry is left unchanged. If a later CSV no longer contains Bob, PassMan
deletes Bob's Apple-managed entry after showing that deletion in the
confirmation. Importing the same CSV again leaves current entries unchanged.
Separate usernames at the same website are kept as separate entries.
Passwords retain leading and trailing spaces exactly. A blank Password cell
in a complete CSV row clears the saved password for the matching Apple-managed
entry. If a unique account's URL path changes while its website host and
username stay the same, PassMan keeps its existing entry ID and custom fields.
Malformed URLs or incomplete CSV rows stop the import before changes are made.

PassMan matches Apple-managed accounts by normalized website and username. For
records without a username, it can match by website and title. If multiple
existing Apple-managed entries make a match ambiguous, PassMan leaves them
unchanged instead of guessing. Review the counts before confirming, especially
if your vault contains multiple entries with the same website and username.

Only entries created through **Import** are managed by later Apple CSV imports.
Entries created with **Add Entry**, or entries that otherwise have no Apple
import marker, are never overwritten or deleted by this import. If an imported
entry is removed from a later CSV, only that Apple-managed entry is removed;
you must manually delete entries you created yourself. This ownership marker is
stored inside the encrypted vault with the entry.

Entries imported by an earlier PassMan build before source tracking was added
have no ownership marker. PassMan leaves those entries untouched, since it
cannot safely distinguish them from entries created manually. If needed,
manually remove those old copies after confirming that the new import has
created the tracked entries.

The importer maps Apple's **Title**, **URL**, **Username**, **Password**, and
**Notes** columns to PassMan entry fields. Valid `otpauth://` values in the
**OTPAuth** column are imported into PassMan's separate **Authenticator** mode.
Apple-managed authenticator codes are updated or removed only by later imports
that include the **OTPAuth** column. If that column is absent, existing
Apple-imported authenticator codes are left alone. If the column is present
but its cells are empty, the import treats that as no OTPAuth records and will
propose deleting all previously imported Apple authenticator codes. A malformed
nonempty OTPAuth value stops the import before changes are applied. Passkeys
are not included as usable credentials in the CSV import.

For example, an `OTPAuth` cell containing a URI like
`otpauth://totp/Example%3Aalice?secret=JBSWY3DPEHPK3PXP&issuer=Example` creates
an authenticator with issuer `Example` and account name `alice`. The Base32
secret is stored in the encrypted vault and PassMan generates the rotating
code in **Authenticator** mode. This example secret is synthetic; never copy a
real `OTPAuth` value into documentation, chat, or support messages.

The import preview reports password entries and authenticator codes separately.
For each collection, **add** means new Apple-managed data, **update** means a
matching Apple-managed record changed, **unchanged** means the imported record
already matches, and **delete** means an Apple-managed record is absent from the
current CSV. PassMan matches password entries by normalized website and
username (or website and title when there is no username); authenticator codes
are matched by issuer and account name. Ambiguous matches are left untouched.

## Remove the exported file

After confirming the entries are in PassMan, delete the exported CSV and empty
Trash. The file is readable text and may otherwise remain accessible on disk or
in a synced folder. Avoid emailing it, uploading it, or leaving it in Downloads.

Apple does not include Wi-Fi passwords, some passwords shared with a group, or
Sign in with Apple account access in this export. See [Apple's Mac export
instructions](https://support.apple.com/en-ie/guide/passwords/mchl35b12625/mac)
for the current menu labels and export limitations.
