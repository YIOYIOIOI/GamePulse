import { Search } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { errorText } from "../format";
import type { Game, GameSearchResult } from "../types";
import { Modal, Spinner } from "./ui";

/** Finds a game on Steam by name or App ID, then optionally links its GitHub repository. */
export function AddGameDialog({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: (game: Game) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GameSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState<GameSearchResult | null>(null);
  const [repo, setRepo] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError("");
    try {
      setResults(await api.searchGames(query.trim()));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSearching(false);
    }
  };
  const add = async () => {
    if (!picked) return;
    setSaving(true);
    setError("");
    try {
      onAdded(await api.addGame(picked.app_id, repo.trim()));
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };

  return (
    <Modal
      title="添加游戏"
      onClose={onClose}
      width={560}
      footer={
        picked ? (
          <>
            <button className="btn" onClick={() => setPicked(null)}>
              返回
            </button>
            <button
              className="btn primary"
              disabled={saving}
              onClick={() => void add()}
            >
              {saving ? "正在添加…" : "添加"}
            </button>
          </>
        ) : (
          <button className="btn" onClick={onClose}>
            取消
          </button>
        )
      }
    >
      {!picked ? (
        <div className="form">
          <form
            className="search-row"
            onSubmit={(e) => {
              e.preventDefault();
              void search();
            }}
          >
            <span className="search wide">
              <Search size={14} />
              <input
                autoFocus
                aria-label="游戏名称或 Steam App ID"
                placeholder="游戏名称或 Steam App ID"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </span>
            <button
              className="btn primary"
              disabled={searching || !query.trim()}
            >
              搜索
            </button>
          </form>
          {searching && <Spinner label="正在搜索 Steam" />}
          {results && !searching && results.length === 0 && (
            <p className="muted">
              Steam 上没有找到。Steam
              只按游戏的原始名称搜索，可以试试英文名，或直接输入商店页链接里的
              App ID，例如 store.steampowered.com/app/<b>1127400</b>。
            </p>
          )}
          {results && results.length > 0 && (
            <ul className="game-results">
              {results.map((r) => (
                <li key={r.app_id}>
                  <button disabled={r.added} onClick={() => setPicked(r)}>
                    {r.image ? (
                      <img src={r.image} alt="" loading="lazy" />
                    ) : (
                      <span className="game-image-placeholder" />
                    )}
                    <span className="game-result-name">
                      {r.name}
                      <small>App ID {r.app_id}</small>
                    </span>
                    {r.added && <span className="badge">已添加</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {error && <p className="error-text">{error}</p>}
        </div>
      ) : (
        <div className="form">
          <div className="game-picked">
            {picked.image && <img src={picked.image} alt="" />}
            <span>
              <b>{picked.name}</b>
              <small>Steam App ID {picked.app_id}</small>
            </span>
          </div>
          <label>
            <span>
              GitHub 仓库 <span className="optional">可选</span>
            </span>
            <input
              autoFocus
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              placeholder="owner/name 或仓库链接"
            />
          </label>
          <p className="muted">
            关联开发团队的公开仓库后，还会汇总它的 issue
            和版本发布记录，用来做问题对照和版本前后对比。没有公开仓库可以留空，之后也能在设置里关联。
          </p>
          {error && <p className="error-text">{error}</p>}
        </div>
      )}
    </Modal>
  );
}

export function RepoDialog({
  game,
  onClose,
  onSaved,
}: {
  game: Game;
  onClose: () => void;
  onSaved: (game: Game) => void;
}) {
  const [repo, setRepo] = useState(game.repo);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      onSaved(await api.linkRepo(game.key, repo.trim()));
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };
  return (
    <Modal
      title={`${game.name} 的 GitHub 仓库`}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            取消
          </button>
          <button
            className="btn primary"
            disabled={saving}
            onClick={() => void save()}
          >
            保存
          </button>
        </>
      }
    >
      <div className="form">
        <label>
          仓库
          <input
            autoFocus
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/name 或仓库链接；留空表示不关联"
          />
        </label>
        <p className="muted">修改从下一次同步开始生效，已有数据不变。</p>
        {error && <p className="error-text">{error}</p>}
      </div>
    </Modal>
  );
}

export function RemoveGameDialog({
  game,
  onClose,
  onRemoved,
}: {
  game: Game;
  onClose: () => void;
  onRemoved: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const remove = async () => {
    setSaving(true);
    setError("");
    try {
      await api.removeGame(game.key);
      onRemoved();
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };
  return (
    <Modal
      title={`移除 ${game.name}？`}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            取消
          </button>
          <button
            className="btn danger"
            disabled={saving}
            onClick={() => void remove()}
          >
            移除
          </button>
        </>
      }
    >
      <p>
        移除后不再同步这款游戏，它也不会出现在游戏列表里。已经保存的历史数据和跟进记录不会删除。
      </p>
      {error && <p className="error-text">{error}</p>}
    </Modal>
  );
}
