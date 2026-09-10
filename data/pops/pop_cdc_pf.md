# POP – Atendimento de Operações de CDC (Crédito Direto ao Consumidor) – Pessoa Física
### [Versão anonimizada/pseudonimizada para uso acadêmico]

> **Nota metodológica de anonimização:** este documento é uma versão pseudonimizada de uma rotina real de atendimento (SAC) de operações de crédito pessoa física. Foram substituídos: (i) o nome da instituição financeira e de seus canais/site/e-mail; (ii) os nomes de sistemas internos claramente proprietários; (iii) nomes e códigos de convênios de consignação com órgãos públicos; (iv) códigos de prefixo/departamento interno; e (v) números de rotinas/assuntos auxiliares referenciados ao longo do texto — todos substituídos por identificadores fictícios e sequenciais. A lógica processual, as condições, exceções e o fluxo de decisão originais foram mantidos integralmente, o que preserva o valor do documento como exemplo de POP para fins de extração de árvore de decisão. Termos e siglas genéricas do setor bancário (CDC, SAC, Ouvidoria, TAA, URA, FCR, ANC, Token, Identificação Positiva) e referências a normas públicas (Resolução CMN 4.790/2020, INSS) foram mantidos, por não serem exclusivos de uma única instituição.

**Sumário:** Observações iniciais · 1. Consulta geral CDC · 2. Débito da parcela CDC · 3. Simulação/Contratação · 4. Cancelamento de CDC · 5. Liquidação/Amortização · 6. Dificuldade para contratação · 7. Contratação não reconhecida · 8. Limite Especial da Conta · 9. Rotinas auxiliares · 10. Fonte de informação

---

## Observações iniciais

a) Esta rotina destina-se ao atendimento das operações de crédito PF listadas no item 2. Para os casos abaixo, consulte rotinas específicas:
- **FIES:** rotina 50101 – SAC QC – Financiamento Estudantil (FIES)
- **Financiamento imobiliário:** rotina 50102 – SAC QC – Financiamento Imobiliário
- **Renegociação de dívidas:** rotina 50103 – SAC QC – Renegociação de Dívidas Pessoa Física e Jurídica

b) **Autorização de Débito em Conta:** a partir de 01/03/2021, para que uma operação seja debitada em conta, é necessária autorização específica do cliente para o débito. Ver informações e procedimentos na rotina 50104.

c) **Canais para contratação de CDC:** [link para os canais de contratação]

---

## 1. Consulta geral CDC

Para verificar as informações da operação, identifique se o consumidor é PF e titular da operação. Em caso de FALHA, RECUSA ou INAPLICABILIDADE de Identificação Positiva (IP), registre ocorrência.

| Demanda | Consulta |
|---|---|
| a) Informações gerais do CDC | `SISALFA > CDC > 15 > 18` — em "Código do Cliente" pressione F4, inclua o CPF e selecione a operação. Clique em F2 > Outros dados > 4. Cronograma. Principais informações: modalidade do CDC, data de vencimento, parcelas pagas e data de pagamento (mais detalhes no item 2), parcelas a vencer, parcelas em atraso, taxas de juros ou CET. |
| b) Saldo atualizado total | `SISALFA > CDC > 15 > 18` — mesmo caminho acima; após selecionar a operação, verifique o campo "Saldo devedor atual". Esse é o saldo do dia, com atualização diária. |
| c) Parcelas, valores pagos, juros, datas de pagamento | `SISALFA > CDC > 15 > 18` → Agência/Conta → selecione a operação → F2 → 4. Cronograma → selecione a parcela ("P" indica pagamento parcial) → F9 (detalhe) → F12/F11 (pagamentos e parcelas). O "total recebimento parcial" é o valor recebido naquela parcela. |
| d) Consultar CDC liquidado, renovado ou excluído | `SISALFA > CDC > 15 > 18`, em "Código do Cliente" pressione F4 e insira o CPF — NÃO selecione nenhuma operação e pressione F11. F12 para operações arquivadas. |
| e) Consulta de cláusulas gerais ou documentos do CDC contratado | Cláusulas gerais consultáveis em: **App Alfa** (Menu > Empréstimos > Contratar empréstimo > Aderir ao contrato); **site institucional**, inclusive para não correntista (Página inicial > Pra você > Empréstimo > Empréstimo pessoal > Contrato de abertura de crédito rotativo); **site institucional (área logada)** (Menu > Empréstimos > Crédito consignado e pessoal > Aderir Contrato de Empréstimo). Documentos do CDC contratado: Extrato de Empréstimo (parcelas pagas/a pagar) — App, site, caixas eletrônicos ou agências; Consolidado Anual (valores por exercício) — site ou agências; 2ª via do comprovante (com taxas) — App ou agências. |

---

## 2. Débito da parcela CDC (data ou valor divergente, duplicidade)

Para identificar o débito questionado, consulte o extrato em `Plataforma de Relacionamento (Operações Contratadas) > Contas > Consultas > Extrato Conta Corrente`. O número da operação consta no campo "Documento" (9 dígitos).

Situações possíveis: débito antes/depois do vencimento contratual; valor divergente; duplicidade (folha + conta); débito em conta errada.

**Consulta:** `CDC 15.13` (F4 – CPF) → selecione a operação → F2.4 (cronograma) → selecione a parcela com "x" → F9 (detalhar) → F12 (mais informações) → F3 (voltar) e copie o nº da operação → `CDC 13.61` (cole o nº como "nº contrato") para ver como ocorreu o pagamento.

Siga então a orientação por modalidade:

### CDC Consignação ou CDC Renovação Consignação
Débito ocorre na folha de pagamento. a) Se não consignada (ou parcial), o débito ocorrerá total/parcial em conta. b) Se liquidado/renovado mas houve consignação, o estorno é automático em conta em até D+2 dias úteis, exceto para os convênios de código 900001 (INSS — devolução a partir do 5º dia útil) e código 900002 (MPDG — devolução até o 1º dia útil).

1. Consulte a parcela: `CDC 15 > 13 > F2 > 4` (datas); `CDC 15 > 13 > F8 > F9` (mês/ano da folha). *Consig total* = debitada integralmente em folha; *Consig parcial* = debitada parcialmente (verifique o restante em conta); *Não consignada* = sem débito em folha; *Incluída* = ainda não vencida; *Enviada* = empregador não retornou (sem repasse, o débito ocorre em conta).
2. Confirme a consignação em `SISCONSIG 22 > 01 > 01` (Convênio, Data Prevista, nº Operação — dados em `CDC 15.13`); selecione "x" e F9: "Tipo Lançamento" *Amortização* = consignado; *Devolução* = não consignado, devolvido à conta.
3. Preste as informações.
4. Se o cliente disser que a parcela foi consignada em folha mas também há débito agendado em conta: verifique o extrato (agendado ou debitado); se debitado, verifique devolução; se a data for hoje/próximo dia útil, oriente aguardar o processamento noturno (tende a ser excluído) e encerre em FCR. Se confirmada duplicidade sem estorno, ou se o sistema não mostra consignação mas o cliente afirma o desconto, registre ocorrência e oriente o envio de cópia do contracheque para `sacdocumentos@bancoalfa.com.br`.

> **Crédito do Trabalhador** (identifique pelo campo "Convênio" = "E-Consig PJ" em `CDC > 15 > 13`): exigir contracheque da competência anterior ao débito (ex.: débito no mês 09 → contracheque do mês 08) e o documento "Detalhe da guia emitida" (com a instituição que recebeu o valor) + comprovante de pagamento da guia, fornecidos pela empresa.

### CDC Salário, CDC Benefício e CDC Renovação
Débito no dia do crédito do salário/benefício, mesmo que divergente do vencimento contratual (cobrança antecipada gera desconto proporcional). Renovação com convênio: débito na data de crédito de proventos; sem convênio: na data de vencimento.

1. Verifique no extrato o recebimento de salário no dia do débito.
2. Compare a data de débito (`CDC 15 > 13 > F2 > 4`) com a cadastrada em `CDC 24 > 14` e `SISPAG 11 > 13 > 36 > Consulta on line`.
3. Se ambos ocorrerem após o vencimento do contrato, registre ocorrência.
4. Preste as informações.

### CDC Automático
Débito em conta (corrente ou salário) na data de vencimento informada na autorização; há opção de boleto (gerado pelo cliente ou se a autorização foi cancelada).

**Duplicidade:** 1. Verifique boleto pago + débito em conta (`CDC 13 > 61`, "Forma Pagto": Rcbto Autom e Boleto Banc); confira estorno (campo "Dt. Canc." preenchido = houve estorno). 2. Se confirmada duplicidade sem estorno, estorne em `CDC 13 > 91 > 11 > 6` (o sistema só estorna do mais recente para o mais antigo; se o pagamento em conta foi parcial e só for possível estornar o boleto mais recente, isso deixaria a operação em atraso — nesse caso, estorne primeiro o "Boleto Bancário" e depois o "Recebimento Automático", só se não houver débitos pendentes). Peça ao supervisor para receber o valor correto em `CDC 13.23`; confirme a data de recebimento retroativo em `CDC 13.61`.
> Para recebimento por débito em conta em operações contratadas a partir de 01/03/21, é necessária autorização específica do cliente.

### CDC 13º Salário
Débito em parcela única. **Com convênio:** na data de cobrança (recebimento do 13º, informado pelo empregador) OU no vencimento (30 dias após o crédito do 13º), o que ocorrer primeiro — exceto convênios com 13º vinculado ao aniversário do cliente. **Sem convênio:** na data escolhida na contratação.

- Convênio consta em `SISALFA > CDC 15.13`.
- **Com convênio:** data de cobrança em `CDC 22 > 10 > 5d` (código de linha 3100; nº convênio em `CDC 15 > 13`); vencimento em `CDC 15 > 13 > F2 > 4`. 1. Informe que o débito ocorre na data de cobrança; se o 13º não for creditado, tenta-se o débito na data de cobrança ou vencimento (o que ocorrer primeiro). 2. Verifique como ocorreu em `CDC 15 > 13 > F2 > 4`. 3. Preste as informações.
  > **Obs.:** se a data de cobrança mudar por solicitação do empregador, o vencimento pode ser antecipado. *Ex. 1:* cobrança cadastrada 30/06/26 → vencimento 30/07/26; se a cobrança mudar para 30/08/26, cobra-se em 30/07/26 (o que ocorrer primeiro). *Ex. 2:* se o 13º do convênio está vinculado ao mês de aniversário, cobrança e vencimento caem no mês de aniversário do cliente.
- **Sem convênio:** débito no vencimento (`CDC 15 > 13 > F2 > 4`).

### CDC Antecipação IRPF
Débito (a) na data prevista do crédito da restituição, ou (b) no vencimento contratual, se o crédito não ocorrer antes.
1. Informe a regra acima. 2. Consulte `CDC 15 > 13 > F2 > 4`. 3. Preste as informações.

### CDC Antecipação Saque Aniversário FGTS
Liquidação automática via repasse do FGTS; débito em conta só se o repasse for insuficiente.
1. Consulte `CDC 15 > 13 > F2 > 4`. 2. Preste as informações.

### Orientações complementares
a) Reclamação de saldo aprovisionado em fim de semana/feriado: explique que, pelas cláusulas gerais do contrato de conta, a liberação de débitos nesses períodos depende do saldo após deduzir débitos programados para o 1º dia útil seguinte.
b) **Boleto:** algumas linhas permitem gerar boleto (rotina 50107); se houver duplicidade (conta + boleto), estorne como em "CDC Automático". Não aplicar esse procedimento a CDC Consignação/Renovação Consignação/FGTS Saque Aniversário se a forma de pagamento foi "Cta Convênio" — para forma de pagamento via `SISALFA` ou "Boleto Bancário", o estorno é permitido.
c) Mais informações: ver rotinas auxiliares (item 9).
d) Se não for possível identificar o motivo, ou o cliente permanecer insatisfeito, registre ocorrência.

---

## 3. Simulação/Contratação de Empréstimos

CDC é um empréstimo pessoal automatizado, pré-aprovado, disponível em conta corrente. Solicitação exclusiva do titular.
> Se o cliente quiser alterar o vencimento da prestação: após a confirmação do contrato isso não é possível. Alternativa: contratar CDC Renovação (se a linha permitir e houver limite), indicando o vencimento mais adequado.

**Procedimento:** verifique se a Análise de Crédito (ANC) está vigente em `Plataforma de Relacionamento (Operações Contratadas) — aba Limite de Crédito`, campo "Situação do limite".

| Status do limite | Procedimento |
|---|---|
| Vencida, Impedida, Cancelada, Suspensa, Em transferência, Em estudo, Indeferida, ou Vigente com Limite Total–Margem zerado | Informe que não há limite disponível; o cliente deve ir a qualquer agência com identificação (RG/CPF), comprovante de residência e de renda (emitidos há menos de 90 dias, mesmo que pela internet). Consulte a rotina 50105 para possibilidade de restabelecimento. |
| Vigente (algum valor em Limite Total–Margem) | Não informe o valor ao cliente. Dentro do horário de atendimento (9h–18h), pergunte se autoriza transferência para a Central de Consultoria em Uso Responsável do Crédito (rotina 50106). Se não autorizar, ou fora do horário, informe as opções: Central de Consultoria; App Alfa > Empréstimo; site > Empréstimo; caixa eletrônico (TAA) > Empréstimo. |

---

## 4. Cancelamento de CDC

Cancelamento permitido em até 7 dias corridos (a partir do dia seguinte à liberação do crédito), se contratado por canal de autoatendimento (App, site, caixas eletrônicos ou telefone), pelo titular, autenticado (URA, Token ou Identificação Positiva).

> **Atenção:** o cancelamento da linha 2881 – Crédito Renovação Consignação está restrito ao departamento **DOC – Diretoria de Operações de Crédito** (código 800020) para os convênios: Convênio Especial 01 (700001), 02 (700002), 03 (700003), 04 (700004), 05 (700005), 06 (700006), 07 (700007), 08 (700008), 09 (700009), 10 (700010), 11 (700011), 12 (700012), 13 (700013), 14 (700014), 15 (700015) e 16 (700016). É necessário haver margem suficiente para reaverbação das operações vinculadas à renovação cancelada.
> O cancelamento da mesma linha para o Convênio Especial 17 (700017) está restrito à **Superintendência Regional III** (código 800030). Ver rotina 50108.

Antes do procedimento, informe o número da operação e que, após o cancelamento, o comando não pode ser desfeito.

### 4.1. Cancelamento de proposta CDC NÃO CONFIRMADA
`SISRET Y09` — copie o nº da operação (documento, 9 dígitos). `CDC 11.13` → inclua o nº a cancelar. Em "Exclusão de operação – Confirma?", responda "S". Motivo: "08 – Exclusão a pedido do cliente – Desistência". Verifique a mensagem "Cancelamento da Proposta efetuado em XX/XX/XX às XX:XX:XX por FXXXXX"; se diferente, registre ocorrência.
> Atenção a operações via Correspondente – LOG 633 "Operação Novo Fluxo Correspondente/Parceiro Comercial" (`CDC 15.18.F2.8`). Se pendente de confirmação, registre ocorrência (motivo obrigatório; não oriente o cliente a excluir por autoatendimento).

### 4.2. Cancelamento no MESMO DIA ou DIA ÚTIL SEGUINTE (contratação em dia não útil)
Permitido para contratações presenciais e não presenciais, todos os canais. Uso do Limite Especial da Conta gera juros e IOF. Cancele em `CDC 14`; se falhar, registre ocorrência.

### 4.3. Cancelamento em até 7 DIAS CORRIDOS (a partir do dia seguinte ao crédito)
**Via TAA/internet/App/telefone (Duplo Sim):** consulte `CDC 15.18.F2.8` (log) — canal no log 201: *Duplo Sim* → campo "Ocor" LOG 201 e 493; *Correspondente* → registre ocorrência. (Contestação: ver item 7.2.)
**Presencial na agência:** só cancela no mesmo dia (ver item 4.2)! A partir do dia seguinte, só liquidação. Se o cliente relatar falhas, registre ocorrência.

Verifique saldo para o débito (ou "troco" nas Renovações — `CDC 15.18.F2.5 Contratos Vinculados` mostrará o `SISCLI`; informe o valor), considerando Limite Especial ou resgates automáticos. Oriente manter saldo (débito à noite); uso do Limite Especial gera juros/IOF. Se discordar, só liquidação/amortização/pagamento. Cancele em `CDC 14`; se falhar, registre ocorrência.
> No cancelamento de CDC Antecipação Saque Aniversário FGTS, o desbloqueio da garantia é automático. Log "1120 – Operação Contratada com Parcela Pix" = produto Alfa Parcela Pix (mesmo procedimento de Duplo Sim).

### 4.4. Cancelamento de REPACTUAÇÃO
`CDC 15.13`, selecione a operação. Se constar "Op" pendente de confirmação, pode excluir; se confirmada, só liquida/paga total.
> *Convênio Especial 17:* tem repactuação de CDCs consignados com suspensão de cobrança (rotina 50109).

### 4.5. Cancelamento do produto de pagamento parcelado de contas
Ver item 10 da rotina 50110.

### 4.6. Pedido após 7 dias, ou contratação presencial (pedido fora do mesmo dia)
Só é possível a liquidação.
> Obs. 1: presencial só cancela no mesmo dia (item 4.2). Obs. 2: exclusivamente para CDC Renovação, se a liquidação antecipada não puder ser feita, registre ocorrência para avaliar cancelamento (informar que o IOF será cobrado em conta). CDC Renovação sem "troco" é cancelável se a contratação não foi presencial e o pedido ocorreu em até 7 dias.

Cancele em `CDC > 14`. Em caso de erro, registre ocorrência.

---

## 5. Liquidação / Amortização

Solicitação exclusiva do titular.

### 5.1. Amortização/Liquidação ANTECIPADA ou operação EM ATRASO
**Demanda:** quitação parcial/total antes do vencimento e/ou parcelas em atraso.
> Pagamento via boleto: emitido em agência, pago no mesmo dia (saldo atualiza diariamente); se não pago no mesmo dia, o mesmo boleto ainda serve, pois o saldo é recalculado.

Se não autenticado (URA/Token/IP), informe os canais. Cancelamento da amortização/liquidação só no mesmo dia, e só com margem disponível (item 5.3). Somente com recursos próprios; há redução proporcional de juros.

**Tipos** (parcelas em atraso sempre em ordem crescente): **Crescente** (da próxima parcela em diante); **Decrescente** (da última parcela para trás); **Linear** (amortiza o saldo total sem alterar o cronograma; recalcula as parcelas a vencer).
> Linear NÃO permitido para CDC Consignado, nem para operações fora do status "Normal", com pagamento parcial, em cobrança, ou com "Pula-Parcela". "Em cobrança" não aceita nenhuma amortização.

| Necessidade do cliente | Tipo de amortização |
|---|---|
| Parar de pagar as próximas prestações por um período | Liquidação antecipada de parcelas integrais, ordem crescente |
| Amortizar e continuar pagando as próximas prestações | Liquidação antecipada de parcelas integrais, ordem decrescente |
| Reduzir o valor das prestações em toda a operação | Amortização linear |
| Liquidar a operação | Quitação total, sempre em ordem crescente |

> No CDC Consignado, pode haver desconto da próxima prestação em folha. Para Consignação/Renovação Consignação, prefira ordem decrescente (evita duplicidade em folha); se o cliente pedir crescente, informe o risco (o valor retorna no vencimento da parcela, se ocorrer).

**Procedimento:** 1. Simule em `CDC 13.11.12`, informe o saldo atual (item 1b). 2. Verifique saldo suficiente (`Plataforma de Relacionamento > Contas > Extrato`), considerando saldo aprovisionado, tarifas pendentes, resgates automáticos e Limite Especial (a critério do cliente, com encargos). 3. Se insuficiente, oriente novo contato; se suficiente, execute em `CDC 13 > 21 > 12` (tipo: parcial/liquidação/linear; quantidade/valor; ordem).
> Se o sistema indicar ausência de autorização de débito, siga a rotina 50104.

**Leitura obrigatória ao cliente antes da confirmação** ("Sr(a). ___, para sua segurança, faremos a leitura das condições:"):
- **Parcial/liquidação:** agência/conta; valor base da parcela; encargos por atraso; desconto de antecipação; variação Selic; valor a amortizar; total de parcelas; ordem escolhida.
- **Linear:** valor base; desconto aproximado; variação Selic; valor da parcela inicial; novo valor da parcela; quantidade de parcelas.

Após a leitura: "Podemos confirmar a liquidação/amortização?" (F3, sem impressão). Supervisor confirma em `CDC 13.21.52`. Informar necessidade de saldo em conta. Comprovante: "o débito ocorre ainda hoje; confirme pelo extrato. Para comprovante detalhado, solicite em qualquer agência o documento 'Demonstrativo de Origem e Evolução de Dívida – Crédito Direto ao Consumidor'."

### 5.2. Amortização/liquidação de operações "EM PERDAS"
Identificação: `SISALFA > CDC > 15.13`. **Não informar ao cliente que a operação está em prejuízo.**
a) **Débito em conta:** verifique saldo suficiente (mesmas ressalvas do item 5.1); se insuficiente, oriente novo contato. Liquidação: comando em `CDC 13-34` + confirmação do supervisor em `CDC 13-36`. Amortização parcial: comando em `CDC 13-35` + confirmação do gerente de grupo em `CDC 13-36`.
b) **Boleto bancário:** registre ocorrência.

### 5.3. Cancelamento da amortização ou liquidação antecipada
Se só houve o comando do atendente (`CDC 13.21.12`) no mesmo dia: cancele em `CDC 13.91.51`. Se já confirmado pelo supervisor (`CDC 13.21.52`): faça o estorno (item 5.5).
> O registro do atendente fica pendente de confirmação apenas no mesmo dia; se não confirmado, é excluído automaticamente no dia seguinte.

### 5.4. Liquidação – Desaverbação/Liberação de Margem Consignável
Se o cliente relatar que liquidou/cancelou mas não houve liberação de margem, ou a parcela segue sendo debitada, registre ocorrência.

### 5.5. Estorno de pagamento antecipado
**Demanda:** pagamento antes do vencimento, ou débito indevido em conta (ex.: pela agência).
> Não aplicar a Consignação/Renovação Consignação/FGTS Saque Aniversário se a forma de pagamento foi "Cta Convênio"; para `SISALFA` ou "Boleto Bancário", o estorno é permitido (ver item 2).

1. Analise o motivo (não é permitido estornar e deixar em atraso). 2. Verifique vencimento (`CDC 15.13.F2.4`) e pagamento de salário (`SISPAG 11 > 13 > 36 > Consulta on line`). 3. Se não venceu e não houve crédito de salário, estorno possível (pagamento dentro de 30 dias, operação não atualizada). 4. Estorne em `CDC 13.91.11`. 5. Informe crédito no processamento noturno.
> Se impossível estornar, ou outra duplicidade não sanável, registre ocorrência.

---

## 6. Dificuldade para contratação

| Situação | Procedimento |
|---|---|
| **Renda desatualizada** | Verifique a última atualização; se >12 meses, oriente atualizar via App ou canal de autoatendimento (online; às vezes exige foto do documento, validação em até 3 dias úteis). Após validação, o limite é recalculado automaticamente. |
| **Contrato do CDC não assinado** | Pergunte se aderiu às Cláusulas Gerais (assinatura da Proposta/Contrato de Adesão). Se sim, prossiga a análise. Se não, informe os canais de adesão: App/site (Empréstimo > Solicitação de Crédito > Assinatura de contrato CDC); caixa eletrônico; agência. |
| **Acordo de dívida vigente** | Contratação impossibilitada durante a vigência do acordo; após encerrado, pode verificar novamente. |
| **Não correntista** | Exceto CDC Consignado e Crédito 13º Salário INSS (exigem ANC vigente), as demais linhas exigem conta corrente com ANC vigente. |
| **Modalidade de conta simplificada (sem linhas de crédito)** | Não permite contratar linhas de crédito; se houver interesse, o cliente faz upgrade da conta pelo app (Menu > Upgrade de Conta), sujeito a análise de crédito na agência. |

---

## 7. Contratação não reconhecida

### 7.1. Falsidade ideológica e fraude
Fraude com uso de documentos falsos para contratar produtos; a vítima costuma descobrir só quando seu CPF/CNPJ sofre restrição por inadimplência. Ver rotina 50111.
- Falsidade em operação de não correntista: oriente comparecimento a qualquer agência com identificação e boletim de ocorrência.
- Fraude – demais situações: ver rotina 50112.

### 7.2. Contestação de operações via Correspondente (falha, suspeita de fraude/golpe)
Indícios de falha ou fraude/golpe (presencial ou Duplo Sim): registre ocorrência e responsabilize a unidade de correspondentes/antifraude (código 800010):
- **Assunto 50113** — contratação não reconhecida; divergente do solicitado; insatisfação com o contrato/descumprimento; falta de clareza.
- **Assunto 50114** — suspeita de fraude/golpe: abordagem por suposta empresa vinculada ao banco, internalização por correspondente e transferência de recursos a terceiros pelo cliente.
- **Assunto 50115** — contestação/suspeita de fraude em operação via Correspondente ainda pendente de confirmação.

> No módulo de SAC e Ouvidoria (assuntos 50113/50114), é obrigatório selecionar o produto/modalidade — só aparecem operações contratadas via Correspondente; caso contrário, o registro não é possível. Ao selecionar a operação, os dados de identificação do correspondente, do CDC e da chave de operação são preenchidos automaticamente (não editáveis).

---

## 8. Limite Especial da Conta

### 8.1. Cancelamento do Limite Especial da Conta
a) Pode ser solicitado a qualquer tempo por qualquer titular.
b) Ao ser solicitado, sonde o motivo e, se cabível, argumente: sem tarifa; limite disponível para emergências sem custo se não usado; cancelar não garante nova contratação futura; é possível reduzir para R$ 100,00 em vez de cancelar. O cliente não pode estar usando o limite no momento (se estiver, oriente cobrir o saldo). Se aceitar reduzir, siga para 8.2. *(Em Ouvidoria, cancelar direto, sem sondagem.)*
c) Se decidir manter, encerre em FCR.
d) Se insistir no cancelamento, verifique viabilidade:

**Procedimento (cliente autenticado por URA/Token/IP):**
> Não cancelar se o cliente estiver usando o limite; se houver juros/IOF a cobrar, é necessário saldo. Falha de autenticação: registre ocorrência.
- **Atendente:** confira saldo suficiente (extrato) para limite + juros + IOF (desconsiderar valores provisionados); se insuficiente, peça depósito equivalente e informe que o cancelamento pode ser pedido no SAC/agência após o depósito; encerre em FCR. Cancele na plataforma (`Contas > Limite Especial da Conta PF > Implantação, Alteração, Renovação e Cancelamento > Cancelar > Registrar`) e peça deferimento ao supervisor.
  > Se aparecer "(27) Já existe comando de implantação para esta conta.", registre ocorrência. Se aparecer "já existe solicitação pendente de deferimento", peça o deferimento ao supervisor; se não localizar ou houver erro, abra ocorrência.
- **Supervisor:** confirme dados (nome, produto, valor); defira (`Deferimentos e Pendências > Limite Especial da Conta Pessoa > Cancelamento > Deferimento`); confirme para o atendente prosseguir.
- **Atendente:** informe o cancelamento e a disponibilidade da agência para recontratação futura; encerre e registre FCR. *(Se o supervisor não conseguir deferir, registre ocorrência.)*

### 8.2. Redução do Limite Especial da Conta
a) Se o pedido for por causa da tarifa, esclareça que ela não é cobrada; se insistir, siga abaixo.
b) Identifique PF e titular da conta.
c) Cliente autenticado:
- **Atendente:** verifique saldo suficiente para que a redução não deixe o saldo excedido; se preciso, peça depósito e informe que a redução pode ser pedida via app, WhatsApp, SAC ou agência após o depósito. Modalidade "Ouro" (limite ≥ R$ 1.000,00) reduzida para entre R$ 100,00 e R$ 950,00 muda para "Classic" (diferenças na rotina 50116). Se o cliente concordar, altere modalidade/limite na plataforma e peça deferimento ao supervisor.
- **Supervisor:** confirme dados; defira (`Deferimentos e Pendências > Limite Especial da Conta Pessoa Física > Alteração > Deferimento`); confirme para o atendente prosseguir.
- **Atendente:** informe a redução realizada; para elevar no futuro, indicar app/agência. Encerre e registre FCR. *(Se o supervisor não conseguir deferir, registre ocorrência.)*

### 8.3. Alterar data de débito dos juros
Falha de autenticação: informe os canais. Acesse `Plataforma > Contas > Limite Especial da Conta PF > Alterar > Tipo de Alteração – "Dia do débito"` e escolha um dia entre 1 e 28. A alteração só vale a partir do mês seguinte à solicitação.

---

## 9. Rotinas auxiliares (índice de empréstimos)

| Código (anonimizado) | Assunto |
|---|---|
| 50107 | CDC – Condições Gerais / Contrato |
| 50108 | Crédito Consignação e Renovação – Correntista e não correntista |
| 50118 | Crédito Consignação – INSS |
| 50119 | Crédito Automático |
| 50120 | Crédito Benefício |
| 50121 | Crédito Salário e Salário Funci |
| 50122 | Crédito Renovação e Renovação Funci |
| 50123 | Crédito 13º Décimo Terceiro Salário |
| 50124 | Crédito 13º Décimo Terceiro Salário – Não Correntistas |
| 50125 | CDC Antecipação Restituição IRPF |
| 50126 | CDC Antecipação Saque Aniversário FGTS |
| 50117 | Crédito Parcelamento Cheque Especial (Limite Especial da Conta) |
| 50104 | Autorização de Débito – Empréstimos, CDC e outros (Resolução CMN 4.790/2020) |
| 50127 | Crédito do Trabalhador – Novo modelo de Crédito Consignado do Setor Privado |
| 50128 | Crédito do Trabalhador – Atendimento ao Empregador |

---

## 10. Fonte de informação

Departamento responsável: **DOC – Diretoria de Operações de Crédito** (código 800020).
