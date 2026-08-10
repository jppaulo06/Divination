# Changelog

Registro do trabalho de avaliação (DeepEval) feito no backend do Divination. Foco: os testes em si, o que eles encontraram, e o que passam a garantir contra regressão.

## 2026-08-10 — Suíte de testes com DeepEval

### 1. Os testes que implementamos

**`tests/evals/test_answer_unit.py` + `single_turn_metrics.py`** — suíte "unit test" de LLM, single-turn:
- Reaproveita os 25 goldens de `tests/evals/.dataset.json` (a pergunta de abertura de cada um + `expected_outcome`), sem `ConversationSimulator`. Uma chamada ao chatbot + métricas do juiz por golden, sem simular conversa.
- Métricas: `FaithfulnessMetric` (resposta não contradiz o contexto recuperado), `AnswerRelevancyMetric` (resposta endereça a pergunta) e `Rules Correctness` (`GEval` customizado, compara a resposta contra `expected_outcome`).
- Os 4 goldens `*-not-covered` (perguntas fora do escopo do PDF: opportunity attacks, Action Surge, multiclasse, duas spells de concentração) usam um conjunto reduzido de métricas (`NOT_COVERED_METRICS`, sem `AnswerRelevancyMetric`) — ver seção 2.

**`tests/evals/test_divination_chat.py` + `metrics.py`** — suíte conversacional multi-turn (já existia, mas estava completamente quebrada — ver seção 2):
- `ConversationSimulator` gera até 6 turnos de conversa simulada por golden, a partir do `scenario`/`expected_outcome`.
- Métricas: `TurnFaithfulnessMetric`, `ConversationCompletenessMetric`, `RoleAdherenceMetric` (persona "Dungeon Master Assistant") e `Rules Answer Style` (`ConversationalGEval`, formato/estilo da resposta).

**Juiz**: ambas as suítes usam Maritaca `sabia-4` (`eval_model.py`) como avaliador — trocado de `sabiazinho-4` por confiabilidade (ver seção 2).

### 2. O que os testes nos ajudaram a encontrar

Bugs reais de produto, só visíveis depois que a suíte passou a rodar de ponta a ponta:

- **Vector store duplicado (~19x)**: `VectorDatabaseEnricher` reconstrói a coleção do Chroma a partir do PDF a cada inicialização, mas nunca limpava a coleção persistida antes — cada restart do container reinseria os 383 chunks com IDs novos. Depois de várias inicializações, a coleção chegou a **7.277 chunks** (deveria ter 383), degradando o retrieval. Confirmado com uma query que retornou o mesmo chunk errado 4 vezes seguidas.
- **Alucinação em perguntas fora de escopo**: para perguntas que o PDF (só descrições de spell) não cobre, o assistente respondia com conhecimento geral de D&D do próprio modelo em vez de admitir a lacuna — exatamente o comportamento que os goldens `*-not-covered` foram desenhados para pegar.
- **Erro factual real dentro do escopo**: em Counterspell, o assistente afirmou que o slot de magia do inimigo é gasto quando o Counterspell funciona — a regra real diz o contrário.
- **Chunking separa nome do feitiço do corpo**: o `RecursiveCharacterTextSplitter` corta o cabeçalho do feitiço (nome) longe do texto com as mecânicas em alguns casos. O chunk certo às vezes é recuperado, mas sem o nome "Fireball" nele o modelo não confia que aquele trecho responde à pergunta — causa respostas inconsistentes entre execuções idênticas.
- **Juiz `sabiazinho-4` gerava JSON malformado** ocasionalmente nos prompts estruturados do DeepEval, derrubando a coleta inteira da suíte conversacional sem chance de retry — trocado para `sabia-4`.
- **`RoleAdherenceMetric` exigia `chatbot_role`** no test case, e nada no pipeline (golden → simulador → teste) nunca setava isso — a suíte conversacional nunca tinha rodado até o fim antes disso ser descoberto.
- **`AnswerRelevancyMetric` era a métrica errada para os goldens `*-not-covered`**: ela pontua baixo sempre que a resposta não responde literalmente à pergunta — mas para esses goldens, recusar responder *é* o comportamento correto. Isso mascarava respostas corretas como falhas.

### 3. O que os testes garantem (proteção contra regressão)

- **Grounding**: se o RAG voltar a inventar fatos que contradizem o contexto recuperado (dano, DC, alcance, etc.), `FaithfulnessMetric`/`TurnFaithfulnessMetric` pegam.
- **Honestidade em lacunas de escopo**: se o assistente voltar a alucinar respostas para perguntas fora do PDF em vez de admitir a lacuna, `Rules Correctness` (`GEval`) nos 4 goldens `*-not-covered` falha.
- **Correção factual**: para os outros 21 goldens (danos, escalonamento por nível de slot, interações entre spells), `Rules Correctness` compara a resposta contra o `expected_outcome` documentado — captura regressões factuais como a do Counterspell.
- **Persona e formato**: `RoleAdherenceMetric` e `Rules Answer Style` garantem que o assistente continue respondendo como "Dungeon Master Assistant", detalhado, e fechando com "thanks for asking!", conforme `defaultTemplate.txt`.
- **Continuidade conversacional**: `ConversationCompletenessMetric` garante que perguntas de acompanhamento numa mesma conversa continuem sendo resolvidas, não só a pergunta inicial.
- **Saúde do vector store**: nenhuma métrica testa isso diretamente hoje, mas a correção do bug de duplicação (limpar `persist_directory` antes de reconstruir) elimina a causa raiz da degradação silenciosa de retrieval que vínhamos vendo.

### Limitações conhecidas, ainda não corrigidas

- Chunking ainda separa nome de feitiço do corpo em alguns casos (`fireball-upcast-damage`, intermitente).
- Alucinação residual em pelo menos um golden `*-not-covered` (`concentration-two-spells-not-covered`) mesmo com o prompt reforçado.
- Respostas variam entre execuções idênticas (ex: Counterspell, Fireball) — não há determinismo garantido hoje.
