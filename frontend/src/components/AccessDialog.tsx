import { useState } from "react";
import { api, currentWorkspace, setAccess } from "../api";
import { errorText, ROLES } from "../format";
import type { Session } from "../types";
import { Modal } from "./ui";

export function AccessDialog({
  session,
  onClose,
  onChanged,
}: {
  session: Session | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [token, setToken] = useState("");
  const [workspace, setWorkspace] = useState(currentWorkspace());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      await api.checkToken(token, workspace);
      setAccess(token, workspace);
      onChanged();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="登录身份"
      onClose={onClose}
      footer={
        <>
          {session?.team_mode && (
            <button
              className="btn"
              onClick={() => {
                setAccess("", "main");
                onChanged();
              }}
            >
              退出登录
            </button>
          )}
          <button
            className="btn primary"
            form="access-form"
            disabled={busy || !token.trim()}
          >
            登录
          </button>
        </>
      }
    >
      <form
        id="access-form"
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          void connect();
        }}
      >
        {session && (
          <p className="muted">
            当前：{session.principal.name}（
            {ROLES[session.principal.role]?.label}）· 工作区{" "}
            {session.principal.workspace}
            {session.team_mode ? "" : " · 本机单人模式"}
          </p>
        )}
        <p className="muted">
          团队模式下，请使用管理员发放的访问令牌或企业单点登录令牌。令牌只保存在当前浏览器标签页。
        </p>
        <label>
          工作区
          <input
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label>
          访问令牌
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
          />
        </label>
        {error && <p className="error-text">{error}</p>}
      </form>
    </Modal>
  );
}
