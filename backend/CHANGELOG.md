# Changelog

Registro do trabalho de avaliação (DeepEval) feito no backend do Divination. Foco: os testes em si, o que eles encontraram, e o que passam a garantir contra regressão.

## 2026-08-12 — Camada de monitoramento (CD4AI estágio 2)

Ver `MONITORING.md` para o detalhamento do design, como rodar e as lacunas conhecidas.

### O que foi construído

- **Primeira base de dados do projeto.** Até aqui não havia nenhuma persistência: `ChatRepository` é um dicionário em memória e o histórico morria com o processo (`chroma.sqlite3` é arquivo interno do Chroma, não banco da aplicação). Foram criadas 5 tabelas via SQLAlchemy — `interactions`, `retrieved_chunks`, `signals`, `feedback`, `curation_reviews` — com Postgres no `docker-compose` e fallback para SQLite quando `MONITORING_DATABASE_URL` não está definida (testes e scripts não precisam de container).
- **Captura em caminho único.** `ChatService.get_answer` e `get_answer_with_context` passaram a compartilhar um único `_answer`. O caminho de produção agora carrega os documentos recuperados, que antes só o harness de eval via — sem eles, uma interação capturada nunca poderia virar teste de grounding, porque `FaithfulnessMetric` precisa de `retrieval_context`.
- **Versionamento por interação.** Cada interação registra `template_name`, `template_hash`, `corpus_version` e `model`. `POST /v1/context` reescreve o prompt ativo em tempo de execução, então duas perguntas idênticas podem legitimamente gerar respostas diferentes; sem o stamp, regressão de prompt é indistinguível de ruído do modelo.
- **Scores de retrieval.** `ScoredRetriever` substitui `as_retriever()`, que descartava os scores de similaridade. Sem eles o sinal mais barato e mais informativo de falha de RAG — "o melhor chunk era fraco" — não existe.
- **Cinco detectores** offline e determinísticos (sem LLM, sem embeddings): `weak_retrieval`, `unsupported_claim`, `refusal_or_hedge`, `format_guardrail_violation`, `repeated_question`. Rodam como background task após a resposta e via `scripts/run_detectors.py` para recomputar o histórico.
- **Endpoint de feedback** (`POST /v1/feedback`) e **inbox de curadoria** (`GET /v1/monitoring/candidates` e `/summary`).
- **Gerador de tráfego sintético** (`scripts/generate_traffic.py` + banco de ~54 perguntas fora dos 25 goldens: spells não cobertos, regras fora de escopo, perguntas em português contra corpus em inglês, e prompts adversariais). Sem tráfego, a camada de monitoramento não sinaliza nada e não é demonstrável.
- **66 testes** offline em `tests/monitoring/`, rodando no CI a cada PR sem precisar de chaves de API.

### Decisões de design que importam

- **`signals` é índice de seleção, não payload.** Um sinal é uma suspeita gerada por máquina sobre uma interação — não é veredito nem relatório de bug. O estágio otimiza **recall** e aceita falsos positivos de propósito; separar ruído de defeito real é trabalho da curadoria. A curadoria lê `interactions JOIN signals` mais os chunks, porque não se julga um `unsupported_claim` sem ver o que o modelo recebeu.
- **Feedback negativo e seu sinal são gravados na mesma transação.** Todo outro sinal é derivado e recomputável: se um detector falhar, `interactions` + `retrieved_chunks` continuam sendo a fonte da verdade e basta rodar de novo. Um thumbs-down não: nenhum replay o reconstrói, porque a pessoa que o deu já foi embora. Por isso ele não é derivado por varredura posterior — feedback negativo sem sinal é impossível por construção.
- **`feedback` é append-only.** Mudança de nota gera nova linha, então `details.feedback_id` sempre aponta para uma linha que ainda diz o que dizia quando o sinal foi levantado. Notas negativas repetidas preservam todas as avaliações mas geram um único sinal — um sinal já basta para enfileirar, e um segundo violaria a chave de unicidade e derrubaria a avaliação junto.
- **"Aguardando revisão" é a ausência de linha em `curation_reviews`**, não uma coluna de status em `interactions`. Coluna de status duplicaria estado que a tabela de review já implica, e as duas divergiriam.
- **Monitoramento nunca derruba produção.** `record_interaction` engole as próprias falhas e devolve `None`; banco inacessível degrada para "não está gravando" em vez de derrubar o chatbot. O feedback é a exceção deliberada: ele retorna erro, porque o dado é irrecuperável.
- **A inserção da interação é síncrona**, os detectores não. A resposta carrega o `interaction_id` para o cliente anexar feedback, então a linha precisa existir antes do retorno; os detectores leem do banco depois e não custam latência ao usuário.

### Imprecisões deliberadas

- `unsupported_claim` sinaliza respostas corretas cujos números são **derivados**: Fireball em 5º nível é 10d6, que nunca aparece num corpus que diz "8d6 mais 1d6 por nível de espaço acima do 3º". Apertar o detector para calar esse caso custaria recall em alucinações reais.
- `refusal_or_hedge` dispara majoritariamente em comportamento correto — o prompt manda admitir lacunas. O valor está no agregado: um agrupamento de recusas sobre um mesmo assunto é lacuna de cobertura do corpus.
- O limiar de `weak_retrieval` (0.7) é **placeholder** e precisa ser calibrado contra a distribuição real de `retrieved_chunks.score`.

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
