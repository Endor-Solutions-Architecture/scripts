using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"dKy9YVerF9_v","alg":"RS256","n":"0fVEZL-7nev5Xy_BLvetZCncaYWn8PnxtaC6toe76JCI6yxb","e":"AQAB","p":"nWuENjLnr4PIVeqBtfUX_1qm2s2otTQ4SsDJaFCNEA9AvD_t","q":"w6cfpGEzRs9GPczm0dJCqJCFGxoUMpwMqjf5H77nphhhDGZP","dp":"tfZQKu1km4ppRnN_YCXPTOv5DbE8fwPFLiAI_xLIgc6dFlOG","dq":"IzhSWmls0Kkd7vGjItd-T2-3HOwbFK0eAB_gxonQ0dVtBhAO"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"dKy9YVerF9_v\",\"alg\":\"RS256\",\"n\":\"0fVEZL-7nev5Xy_BLvetZCncaYWn8PnxtaC6toe76JCI6yxb\",\"e\":\"AQAB\",\"p\":\"nWuENjLnr4PIVeqBtfUX_1qm2s2otTQ4SsDJaFCNEA9AvD_t\",\"q\":\"w6cfpGEzRs9GPczm0dJCqJCFGxoUMpwMqjf5H77nphhhDGZP\",\"dp\":\"tfZQKu1km4ppRnN_YCXPTOv5DbE8fwPFLiAI_xLIgc6dFlOG\",\"dq\":\"IzhSWmls0Kkd7vGjItd-T2-3HOwbFK0eAB_gxonQ0dVtBhAO\"}";
    var key = new JsonWebKey(jwk);
  }
}
