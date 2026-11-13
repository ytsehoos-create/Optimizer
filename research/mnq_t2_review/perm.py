from common import *
import pickle
E = pickle.load(open("exp.pkl", "rb"))["E15"]
b15 = pd.read_pickle("tr15.pkl"); t3 = b15[b15.id == "T3"].copy(); t3["exp"] = t3.entry_t.dt.strftime("%Y-%m-%d").map(E); t3 = t3.dropna(subset=["exp"])
t3["Rm"] = t3.pnl / t3.meta.apply(lambda m: m["risk"])
rng = np.random.default_rng(3)
for th in (1.6, 1.7):
    lo = (t3.exp <= th).values; obs = t3.Rm[lo].mean() - t3.Rm[~lo].mean()
    perm = np.array([(lambda p: t3.Rm.values[p].mean() - t3.Rm.values[~p].mean())(rng.permutation(lo)) for _ in range(20000)])
    print("threshold %.1f: n %d / %d, mean R %.2f vs %.2f, p = %.4f" % (th, lo.sum(), (~lo).sum(), t3.Rm[lo].mean(), t3.Rm[~lo].mean(), (np.abs(perm) >= abs(obs)).mean()))
