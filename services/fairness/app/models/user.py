from app import db


# DAY-1 SPLIT NOTE / TODO(day-2):
# The User table is OWNED BY THE HOUSEHOLD SERVICE. Fairness must not keep its own
# copy of it. It exists here only so this service boots and the existing fairness
# test (which creates users then calculates scores) still runs unchanged after the
# mechanical split.
#
# On day 2 this model is deleted. calculate_fairness() and the /fairness route stop
# reading User.query and instead fetch the household member list over HTTP from the
# household service, and contribution_score.user_id becomes a plain id with no local
# user row behind it.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)
